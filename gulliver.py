#!/usr/bin/python

import json
import time
import re
import random
import sched
import uuid

# Gulliver: simulates XLD activity for various applications & environments
#
# TODO:
# - make deployments fail / succeed randomly

### from semver library:

_REGEX = re.compile('^(?P<major>(?:0|[1-9][0-9]*))'
                    '\.(?P<minor>(?:0|[1-9][0-9]*))'
                    '\.(?P<patch>(?:0|[1-9][0-9]*))'
                    '(\-(?P<prerelease>[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?'
                    '(\+(?P<build>[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?$')

_LAST_NUMBER = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')

if not hasattr(__builtins__, 'cmp'):
    cmp = lambda a, b: (a > b) - (a < b)

def parse(version):
    """
    Parse version to major, minor, patch, pre-release, build parts.
    """
    match = _REGEX.match(version)
    if match is None:
        raise ValueError('%s is not valid SemVer string' % version)

    verinfo = match.groupdict()

    verinfo['major'] = int(verinfo['major'])
    verinfo['minor'] = int(verinfo['minor'])
    verinfo['patch'] = int(verinfo['patch'])

    return verinfo

def format_version(major, minor, patch, prerelease=None, build=None):
    version = "%d.%d.%d" % (major, minor, patch)
    if prerelease is not None:
        version = version + "-%s" % prerelease

    if build is not None:
        version = version + "+%s" % build

    return version

def bump_major(version):
    verinfo = parse(version)
    return format_version(verinfo['major'] + 1, 0, 0)

def bump_minor(version):
    verinfo = parse(version)
    return format_version(verinfo['major'], verinfo['minor'] + 1, 0)

def bump_patch(version):
    verinfo = parse(version)
    return format_version(verinfo['major'], verinfo['minor'], verinfo['patch'] + 1)

#### end semver



#### SETUP

def setup(data):
	create_applications(data)
	create_dtap(data)

def create_applications(data):
	for app in data["applications"]:
		name = app["name"]
		print "Ensuring application " + name + " is available"
		app_ci_name = "Applications/" + name
		try:
			app_ci = repository.read(app_ci_name)
			print name + " exists"
		except:
			print name + " not found, creating"
			app_ci = factory.configurationItem(app_ci_name, 'udm.Application', {})
			repository.create(app_ci)

def create_dtap(data):
	for app in data["applications"]:
		name = app["name"]
		print "Ensuring DTAP pipeline for application " + name + " is available"

		# Create environments
		env_folder_ci_name = "Environments/" + app["name"]
		create_folder(env_folder_ci_name)
		
		infra_folder_ci_name = "Infrastructure/" + app["name"]
		create_folder(infra_folder_ci_name)

		create_infra(infra_folder_ci_name, create_env(env_folder_ci_name, "DEV"))
		create_infra(infra_folder_ci_name, create_env(env_folder_ci_name, "TEST"), 2)
		create_infra(infra_folder_ci_name, create_env(env_folder_ci_name, "ACC"), 4)
		create_infra(infra_folder_ci_name, create_env(env_folder_ci_name, "PROD"), 9)

def create_folder(ci):
	try:
		repository.read(ci)
		print ci + " exists"
	except:
		print ci + " not found, creating"
		folder_ci = factory.configurationItem(ci, 'core.Directory', {})
		repository.create(folder_ci)

def create_env(ci, name):
	env_ci_name = ci + "/" + name
	env_ci = None
	try:
		env_ci = repository.read(env_ci_name)
		print env_ci_name + " exists"
	except:
		print env_ci_name + " not found, creating"
		env_ci = factory.configurationItem(env_ci_name, 'udm.Environment', {})
		repository.create(env_ci)

	return env_ci

def create_infra(ci, env_ci, hosts = 1):
	name = env_ci.name
	host_ci = None
	for host_idx in range(hosts):
		host_ci_name = ci + "/" + name + "-host-" + str(host_idx)
		try:
			host_ci = repository.read(host_ci_name)
			print host_ci_name + " exists"
		except:
			print host_ci_name + " not found, creating"
			host_ci = factory.configurationItem(host_ci_name, 'overthere.LocalHost', { 'os': 'UNIX' })
			repository.create(host_ci)

		if not (host_ci.id in env_ci.members):
			env_ci.members = [ ci for ci in env_ci.members ] + [ host_ci.id ]
			env_ci = repository.update(env_ci)

#### SETUP

def schedule_next_packages(data):
	next_packages = []

	for app in data["applications"]:
		schedule_next_package(app)

def schedule_next_package(app):
	wait_time = random.randint(int(app["new-version-wait-min"]), int(app["new-version-wait-max"]))
	next_package_time = time.time() + wait_time

	print "Scheduling new package for " + app["name"] + " for " + str(wait_time) + " seconds in the future"
	scheduler.enterabs(next_package_time, 1, create_new_package, (app,) )

def execute_deployment(app, version, env_name):
	env_folder_ci = repository.read("Environments/" + app["name"])
	env_cis = repository.search('udm.Environment', env_folder_ci.id)
	target_env = None
	for env in env_cis:
		if env.endswith(env_name):
			target_env = env

	target_version = repository.read("Applications/" + app["name"] + "/" + version)
	
	print "Executing deployment of " + target_version.id + " to " + target_env

	depl = deployment.prepareInitial(target_version.id, target_env)
	depl = deployment.prepareAutoDeployeds(depl)
	task = deployment.createDeployTask(depl)
	deployit.startTaskAndWait(task.id)

	# TODO: schedule deployment to next stage in pipeline
	try:
		next_env = ENVIRONMENTS[ENVIRONMENTS.index(env_name)+1]
		schedule_deployment(app, version, next_env)
	except:
		# Reached end of pipeline
		print "End of pipeline for " + target_version.id
		pass
	

def create_new_package(app):
	if random.random() < 0.1:
		next_version = bump_major(app["last-version"])
		app["num-deployables"] = str(int(app["num-deployables"]) + random.randint(2,5))
	elif random.random() < 0.2:
		next_version = bump_minor(app["last-version"])
		app["num-deployables"] = str(int(app["num-deployables"]) + random.randint(0,1))
	else:
		next_version = bump_patch(app["last-version"])
	
	package_ci_name = "Applications/" + app["name"] + "/" + next_version
	app_ci = repository.search('udm.Application', app["name"])
	package_ci = factory.configurationItem(package_ci_name, 'udm.DeploymentPackage', { })
	repository.create(package_ci)

	for dep in range(int(app["num-deployables"])):
		file_name = "file-" + str(dep)
		deployable_ci_name = package_ci_name + "/" + file_name
		with open('gulliver.py') as a_file:
			dep_ci = factory.artifactAsInputStream(deployable_ci_name, 'file.File', 
				{ 'targetFileName': file_name, 'targetPath': '/tmp' , 'checksum': str(uuid.uuid4()) }, a_file)
			dep_ci.filename = file_name
			repository.create(dep_ci)

	# Update configuration
	global data
	data = update_config(app["name"], next_version, data)

	# Start deployment pipeline
	schedule_deployment(app, next_version, "DEV")

	# Schedule next package
	schedule_next_package(app)
	scheduler.run()


def schedule_deployment(app, version, env):
	# Schedule start of deployment pipeline
	wait_min = int(app["auto-deploy-wait-min"])
	wait_max = int(app["auto-deploy-wait-max"])

	wait_time = random.randint(wait_min, wait_max)
	start_deploy_time = time.time() + wait_time

	print "Scheduling start of deployment for " + str(wait_time) + " seconds in the future"
	scheduler.enterabs(start_deploy_time, 1, execute_deployment, (app, version, env) )


def update_config(changed_app, new_version, data):
	for app in data["applications"]:
		if app["name"] == changed_app:
			print "Updating version number of " + changed_app + " to " + new_version
			app["last-version"] = new_version

	with open('gulliver-config.json', 'w') as data_file:    
		json.dump(data, data_file)
	
	return data

##########

ENVIRONMENTS = [ "DEV", "TEST", "ACC", "PROD" ]

# Global configuration data
data = None
with open('gulliver-config.json') as data_file:    
    data = json.load(data_file)

# Global scheduler instance
scheduler = sched.scheduler(time.time, time.sleep)

setup(data)
print ""
print ""
schedule_next_packages(data)
scheduler.run()

# Scheduler will run & take all actions, nothing further is needed
