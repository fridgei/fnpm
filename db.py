import json
import re

from flask.ext.sqlalchemy import SQLAlchemy

from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, VARCHAR

from utils import parser, VersionMatcher


db = SQLAlchemy()


class JSONEncodedDict(TypeDecorator):
    """ Encodes and decodes JSON for storage in SQL

    You give it dictionaries as json and it dumps them as strings and stores
    them as VARCHARS.  When you ask for the json from the field it will give
    you the dictionary representation.
    """

    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return None
        return json.loads(value)


class SemverType(TypeDecorator):
   
    impl = VARCHAR
    
    def process_bind_param(self, value, dialect):
        if not value:
            return None
        try:
            parser(value).V()
        except:
            raise InvalidVersion(
                "{0} is not a valid version".format(value)
            )
        return value

    def process_result_param(self, value, dialect):
        if not value:
            return None
        return parser(value).RULE()[0]


class Package(db.Model):
    """Model for storing metadata regarding a Package

    This model is used for storing package metadata returned by the
    /<package_name> route which returns json of the form
    .. code-block:: javascript
        :linenos:
            {
              "_id": "registry",
              "_rev": "33-55c69be715a3b60e4968c809487493ec",
              "name": "registry",
              "description": "Experimental namespaced IoC container",
              "dist-tags": {
                "latest": "0.3.0"
              },
              "versions": {
                "stuff": "version data goes here"
              },
              "words": "more shit"
            }
    """
    __tablename__ = "package"
    id = db.Column(db.Integer, primary_key=True)
    package_name = db.Column(db.String, unique=True, nullable=False)
    json_data = db.Column(JSONEncodedDict, unique=True, nullable=False)
    versions = db.relationship("Version", backref="package")

    def __init__(self, package, json_data):
        """Construction of a Package

        Args:
            package (str): The name of the package we are storing.
            json_data (dict): The json metadata for the package.
        """

        self.package_name = package
        self.json_data = json_data

    def __repr__(self):
        return '<name %r>' % (self.package_name)

    def to_json(self):
        data = self.json_data
        data['latest'] = self.get_latest_version().version
        data['versions'] = {v.version: v.json_data for v in self.versions}
        return data

    def is_local(self, other):
        other = parser(other).LOL()

        if any(other.startswith(x) for x in ('<', '>')):
            other = other.replace(' ', '')
            matchers = [
                VersionMatcher(patt) for patt in re.findall(relative_re, other)
            ]
            return any(
                all(matcher == VersionMatcher(v.version) for matcher in matchers)
                for v in self.versions
            )
        return any(
            VersionMatcher(other) == VersionMatcher(v.version) for v in self.versions
        )

    def get_version(self, version):
        for local in self.versions:
            if VersionMatcher(local.version) == VersionMatcher(version):
                return local 
        return None

    def get_latest_vesrion(self):
        return max(self.versions, key=VersionMatcher)
    

class Version(db.Model):
    """ Model for storing meta data for a specfici version of a Package

    This model has a forien key to packages and specifies the data related to a
    given version of a package.  returned by /<packagename>/<version>

.. code-block:: javascript
        :linenos:
        {
          0.2.2": {
            "name": "registry",
            "description": "Experimental namespaced IoC container",
            "author": {
              "name": "Damon Oehlman",
              "email": "damon.oehlman@sidelab.com"
            },
            "tags": ["ioc"],
            "version": "0.2.2",
            "main": "./pkg/cjs/registry",
            "engines": {
              "node": ">= 0.4.x < 0.9.0"
            },
            "dependencies": {
              "matchme": "0.1.x",
              "wildcard": "*"
            },
            "devDependencies": {
              "expect.js": "0.1.x",
              "mocha": "*"
            },
            "repository": {
              "type": "git",
              "url": "git://github.com/DamonOehlman/register.git"
            },
            "bugs": {
              "url": "http://github.com/DamonOehlman/register/issues"
            },
            "scripts": {
              "test": "mocha --reporter spec"
            },
            "contributors": [],
            "readme": "words",
            "_id": "registry@0.2.2",
            "dist": {
              "shasum": "e7d231b535fd59492c588fc8d6e192156b120018",
              "tarball": "http://registry.npmjs.org/registry/-/registry-0.2.2.tgz"
            },
            "maintainers": [
              {
                "name": "damonoehlman",
                "email": "damon.oehlman@sidelab.com"
              }
            ],
            "directories": {}
          }
        }
    """
    __tablename__ = "version"
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.String, db.ForeignKey('package.id'))
    version = db.Column(SemverType, unique=False, nullable=False)
    json_data = db.Column(JSONEncodedDict, unique=True, nullable=False)

    def __init__(self, version, json_data):
        self.version = version
        self.json_data = json_data

    def __repr__(self):
        return "<{0}>".format(self.version)
