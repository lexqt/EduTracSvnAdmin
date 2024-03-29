# SVNAdmin plugin

from setuptools import setup, find_packages

setup(
    name = 'EduTracSVNAdmin', 
    version = '0.2.5',
    description = 'SVNAdmin for EduTrac',
    long_description = """
		SVNAdmin plugin provides API and administration panels to
		manage Subversion repositories and users.
		Also plugin provides AccountManager listener for user data
		replication into SVN password file.
	""",
    author = 'Evolonix, Aleksey A. Porfirov',
    author_email = 'lexqt@yandex.ru',
    license = 'BSD',
    classifiers = [
        'Environment :: Web Environment',
        'Framework :: Trac',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Version Control',
    ],
    packages = find_packages(exclude=['*.tests*']),
    entry_points = """
        [trac.plugins]
        svnadmin.acct_mgr_listener = svnadmin.acct_mgr_listener
        svnadmin.admin = svnadmin.admin
        svnadmin.api = svnadmin.api
    """,
    package_data = {
    	'svnadmin': [
    		'templates/*.html',
    		'htdocs/css/*.css',
    		'htdocs/images/*'
    	]
    },
)

#### AUTHORS ####
## Author of original TracSVNAdmin:
## Evolonix
## info@evolonix.com
##
## Author of TracSVNAuthz (integrated in this plugin):
## Ian Jones
## ian.trachacks@shrtcww.com
##
## Author of EduTrac adaptation, fixes and enhancements:
## Aleksey A. Porfirov
## lexqt@yandex.ru
## github: lexqt
