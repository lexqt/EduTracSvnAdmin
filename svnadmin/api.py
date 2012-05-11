# SVNAdmin plugin

import os
import os.path
import subprocess
import shutil

from trac.config import Option, BoolOption
from trac.core import *
from trac.util.text import exception_to_unicode
from trac.util.translation import _
from trac.versioncontrol import IRepositoryProvider, RepositoryManager

class SvnRepositoryProvider(Component):
    """Component providing repositories registered in the SVN parent directory."""

    implements(IRepositoryProvider)
    
    svnadmin = Option('svnadmin', 'svnadmin_location', 'svnadmin',
         'Subversion admin executable location')
    svnclient = Option('svnadmin', 'svn_client_location', 'svn',
         'Subversion client executable location')

    parentpath = Option('svnadmin', 'parent_path', '',
         'Parent directory of the repositories (SVNParentPath)')
    hookspath = Option('svnadmin', 'hooks_path', '',
         'Path to copy hooks from')

    create_base_structure = BoolOption('svnadmin', 'create_base_structure', 'false',
         'Create base structure (trunk, branches, tags) for new repository.')
    chmod = Option('svnadmin', 'chmod', '',
         '`chmod` command arguments to perform on new repos. '
         'Leave empty to do nothing.')

    def get_repositories(self, project_id=None, syllabus_id=None):
        """Retrieve repositories in the SVN parent directory."""
        if not self.parentpath or not os.path.exists(self.parentpath):
            return []
        repos = os.listdir(self.parentpath)
        reponames = {}
        for name in repos:
            dir = os.path.join(self.parentpath, name)
            
            command = self.svnadmin + ' verify "%s"' % dir
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (result, error) = process.communicate()
            
            rev = result[result.rfind('revision') + 9:len(result) - 2]
            displayrev = rev
            if rev == '0':
                rev = ''
                displayrev = ''
            reponames[name] = {
                'dir': dir,
                'rev': rev,
                'display_rev': displayrev
            }
        return reponames.iteritems()
    
    def add_repository(self, name):
        """Add a repository."""
        dir = os.path.join(self.parentpath, name)
        if not os.path.isabs(dir):
            raise TracError(_("The repository directory must be absolute"))
        trunk = os.path.join(dir, 'trunk')
        branches = os.path.join(dir, 'branches')
        tags = os.path.join(dir, 'tags')
        command = u'"{svnadmin}" create "{dir}"'
        if self.create_base_structure:
            command += '; "{svn}" mkdir --parents -q -m "Created Folders" "file://{trunk}" "file://{branches}" "file://{tags}"'
        if self.chmod:
            command += '; chmod {chmod} "{dir}"'
        command = command.format(
            svnadmin=self.svnadmin,
            dir=dir,
            svn=self.svnclient,
            trunk=trunk,
            branches=branches,
            tags=tags,
            chmod=self.chmod,
        )
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (result, error) = process.communicate()
        if error is not None and error != "":
            if error.find('E165002') > -1:
                raise TracError(_('The repository "%(name)s" already exists.', name=name))
            elif error.find('E000002') > -1 or error.find('E000013') > -1:
                raise TracError(_("Can't create the repository '%(name)s.' "
                                  "Make sure the parent directory '%(parentpath)s' exists "
                                  "and the web server has write permissions for it.", name=name, parentpath=self.parentpath))
            else:
                raise TracError(error)
        if self.hookspath and os.path.exists(self.hookspath):
            hooksdir = os.path.join(dir, 'hooks/')
            files = os.listdir(self.hookspath)
            files = [os.path.join(self.hookspath, filename) for filename in files]
            for f in files:
                shutil.copy2(f, hooksdir)
        rm = RepositoryManager(self.env)
        rm.reload_repositories()
    
    def remove_repository(self, name):
        """Remove a repository."""
        try:
            dir = os.path.join(self.parentpath, name)
            shutil.rmtree(dir)
            rm = RepositoryManager(self.env)
            rm.reload_repositories()
        except OSError, e:
            raise TracError(exception_to_unicode(e))
