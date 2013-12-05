from db import *
from config import defaults
import requests
from flask import Flask, send_file
import os
import sys
import hashlib
from urlparse import urlparse


class InvalidPackage(Exception):
    pass



def create_upstream_url(package, version):
    return "/".join(
        [app.config['UPSTREAM_REGISTRY'], package, version]
    )


def create_app(test=False):
    app = Flask(
        __name__, static_folder='packages', static_url_path='/packages'
    )
    if test:
        app.config.update(test_defaults)
    else:
        app.config.update(defaults)
    db.app = app
    db.init_app(app)
    return app

app = create_app()
db.create_all()


def get_local_url(package_name, file_name):
    return "/".join(
        [defaults['LOCAL_REGISTRY'], package_name, 'files', file_name]
    )


def get_local_path(project, file_name):
    return os.path.join(defaults['LOCAL_PACKAGE_PATH'], project, file_name)


def is_url(x):
    x = urlparse(x)
    return all([x.scheme, x.netloc])


def download_package(upstream_url, old_sha, file_name, package_name):
    resp = requests.get(upstream_url, stream=True)
    if not resp.status_code is 200:
        raise PackageNotFound(
            "Can not find upstream package {0}".format(upstream_file_url)
        )
    package_path = os.path.join(defaults['LOCAL_PACKAGE_PATH'], package_name)
    if not os.path.exists(package_path):
        os.makedirs(package_path)
    with open(os.path.join(package_path, file_name), 'wb') as f:
        for chunk in (d for d in resp.iter_content(chunk_size=1024) if d):
            f.write(chunk)
        f.flush()
    with open(os.path.join(package_path, file_name)) as f:
        new_sha = hashlib.sha1(f.read()).hexdigest()
        if not new_sha == old_sha:
            raise InvalidPackage(
                "{0} had an invalid sha1 \n{1}\nshould be {2}".format(
                    file_name, old_sha, new_sha
                )
            )
    return get_local_url(package_name, file_name)


def import_package(package_name, version='latest'):
    print "Attempting to import {0} {1}".format(package_name, version)
    # ensure that the version is not a hardcoded url or git repo
    if is_url(version):
        return True
    # get the package metadata if it already exists else create it from
    # the upstream json
    package_obj = Package.query.filter_by(package_name=package_name).first()
    if not package_obj:
        upstream_url = create_upstream_url(package_name, '')
        package_json = requests.get(upstream_url).json()
        # fuck the versions and latest we decide that
        del package_json['versions']
        del package_json['dist-tags']['latest']
        package_obj = Package(package_name, package_json)
    # if we attemt to import latest hit the upstream server
    if version == 'latest' or not package_obj.is_local(version):
        upstream_url = create_upstream_url(package_name, version)
        version_json = requests.get(upstream_url).json()
    else:
        print "{0} {1} already satisfied".format(package_name, version)
        return True
    upstream_url = version_json['dist']['tarball']
    old_sha = version_json['dist']['shasum']
    file_name = upstream_url.split("/")[-1]
    try: 
        version_json['dist']['tarball'] = download_package(
            upstream_url, old_sha, file_name, package_name
        )
    except InvalidPackage as e:
        print >>sys.stderr, str(e)
        return False 
    package_obj.versions.append(Version(version_json['version'], version_json))
    db.session.add(package_obj)
    db.session.commit()
    deps = version_json.get('dependencies', {}).items()
    deps += version_json.get('devDependencies', {}).items()
    for pkg, version in deps:
        import_package(pkg, version)


import_package('brfs', '0.0.8')
import_package('cssauron-falafel', '0.0.3')
import_package('concat-stream', '~1.0.1')
import_package('browserify', '~2.29.1')
import_package('marked', '~0.2.9')
import_package('git-parse-human', '~0.0.1')
import_package('line-stream', '~0.0.3')
import_package('falafel', '~0.3.1')
import_package('plate', '~1.1.2')
import_package('through', '~2.3.4')
import_package('mkdirp', '~0.3.5')
import_package('drive.js', '1.1.4')
