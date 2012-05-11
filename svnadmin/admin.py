# SVNAdmin plugin

import os
import os.path
import subprocess

from genshi.builder import tag

from trac.admin import IAdminPanelProvider
from trac.config import ListOption, Option
from trac.core import *
from trac.util import is_path_below
from trac.util.text import exception_to_unicode
from trac.util.translation import _, tag_
from trac.web.chrome import ITemplateProvider, add_notice, add_warning, add_stylesheet
from trac.web.href import Href
from trac.versioncontrol import DbRepositoryProvider

from svnadmin.api import SvnRepositoryProvider

class SvnAdmin(Component):
    """Component providing svnadmin management of repositories."""
    
    implements(IAdminPanelProvider, ITemplateProvider)
    
    allowed_repository_dir_prefixes = ListOption('versioncontrol',
        'allowed_repository_dir_prefixes', '',
        doc="""Comma-separated list of allowed prefixes for repository
        directories when adding and editing repositories in the repository
        admin panel. If the list is empty, all repository directories are
        allowed. (''since 0.12.1'')""")

    repos_url_prefix = Option('svnadmin', 'repos_url_prefix', '',
         'Default url prefix. If not empty, new repos will got url '
         '`Href(<prefix>)(<repos name>)`.')

    htpasswd = Option('svnadmin', 'htpasswd_location', 'htpasswd',
         'Htpasswd executable location')
    passwd_path = Option('svnadmin', 'passwd_path', '',
         'Path to file with SWV users (AuthUserFile)')

    # IAdminPanelProvider methods
    def get_admin_panels(self, req):
        if 'VERSIONCONTROL_ADMIN' in req.perm:
            yield ('svnadmin', _("SVNAdmin"), 'config', _("Configuration"))
            yield ('svnadmin', _("SVNAdmin"), 'repositories', _("Repositories"))
        if 'TRAC_ADMIN' in req.perm:
            yield ('svnadmin', _("SVNAdmin"), 'authz_raw', _("Edit authz file"))
            yield ('svnadmin', _("SVNAdmin"), 'htpasswd', _("Add / remove SVN users"))

    def render_admin_panel(self, req, category, page, path_info):
        req.perm.require('VERSIONCONTROL_ADMIN')
        
        if page == 'config':
            return self._do_config(req, category, page)
        elif page == 'repositories':
            return self._do_repositories(req, category, page)
        elif page == 'authz_raw':
            req.perm.require('TRAC_ADMIN')
            return self._do_authz_raw(req)
        elif page == 'htpasswd':
            req.perm.require('TRAC_ADMIN')
            return self._do_htpasswd(req)
        
    def _do_config(self, req, category, page):
        parentpath = self.config.get('svnadmin', 'parent_path')
        client = self.config.get('svnadmin', 'svn_client_location')
        admin = self.config.get('svnadmin', 'svnadmin_location')
        hookspath = self.config.get('svnadmin', 'hooks_path')
        
        if req.method == 'POST' and req.args.get('save_settings'):
            parentpath = req.args.get('parentpath')
            client = req.args.get('client')
            admin = req.args.get('admin')
            hookspath = req.args.get('hookspath')
            
            self.config.set('svnadmin', 'parent_path', parentpath)
            self.config.set('svnadmin', 'svn_client_location', client)
            self.config.set('svnadmin', 'svnadmin_location', admin)
            self.config.set('svnadmin', 'hooks_path', hookspath)
            self.config.save()
            add_notice(req, _('The settings have been saved.'))
        
        data = {
            'parentpath': parentpath,
            'client': client,
            'admin': admin,
            'hookspath': hookspath
        }
        add_stylesheet(req, 'svnadmin/css/svnadmin.css')
        return 'config.html', data
    
    def _do_repositories(self, req, category, page):
        # Check that the setttings have been set.
        parentpath = self.config.get('svnadmin', 'parent_path')
        client = self.config.get('svnadmin', 'svn_client_location')
        admin = self.config.get('svnadmin', 'svnadmin_location')
        if not parentpath or not client or not admin:
            add_warning(req, _('You must provide settings before continuing.'))
            req.redirect(req.href.admin(category, 'config'))
        
        data = {}
        
        svn_provider = self.env[SvnRepositoryProvider]
        db_provider = self.env[DbRepositoryProvider]
        
        if req.method == 'POST':
            # Add a repository
            if svn_provider and req.args.get('add_repos'):
                name = req.args.get('name')
                dir = os.path.join(parentpath, name)
                if name is None or name == "" or not dir:
                    add_warning(req, _('Missing arguments to add a repository.'))
                elif self._check_dir(req, dir):
                    try:
                        svn_provider.add_repository(name)
                        db_provider.add_repository(name, 0, dir, 'svn')  # TODO: selectable project_id
                        extra = {}
                        if self.repos_url_prefix:
                            href = Href(self.repos_url_prefix)
                            extra['url'] = href(name)
                        if extra:
                            db_provider.modify_repository(name, extra)
                        add_notice(req, _('The repository "%(name)s" has been '
                                          'added.', name=name))
                        resync = tag.tt('trac-admin $ENV repository resync '
                                        '"%s"' % name)
                        msg = tag_('You should now run %(resync)s to '
                                   'synchronize Trac with the repository.',
                                   resync=resync)
                        add_notice(req, msg)
                        cset_added = tag.tt('trac-admin $ENV changeset '
                                            'added "%s" $REV' % name)
                        msg = tag_('You should also set up a post-commit hook '
                                   'on the repository to call %(cset_added)s '
                                   'for each committed changeset.',
                                   cset_added=cset_added)
                        add_notice(req, msg)
                        req.redirect(req.href.admin(category, page))
                    except TracError, why:
                        add_warning(req, str(why))
            
            # Remove repositories
            elif svn_provider and req.args.get('remove'):
                sel = req.args.getlist('sel')
                if sel:
                    for name in sel:
                        svn_provider.remove_repository(name)
                        db_provider.remove_repository(name)
                    add_notice(req, _('The selected repositories have '
                                      'been removed.'))
                    req.redirect(req.href.admin(category, page))
                add_warning(req, _('No repositories were selected.'))

        # Find repositories that are editable
        repos = {}
        if svn_provider is not None:
            repos = svn_provider.get_repositories()
        
        # Prepare common rendering data
        data.update({'repositories': repos})
        
        add_stylesheet(req, 'svnadmin/css/svnadmin.css')
        return 'repositories.html', data

    def _do_authz_raw(self, req):
        # get default authz file from trac.ini
        authz_file = self.config.get('trac', 'authz_file')

        # test if authz file exists and is writable
        if not os.access(authz_file,os.W_OK|os.R_OK):
            raise TracError("Can't access authz file %s" % authz_file)

        # evaluate forms
        if req.method == 'POST':
            current=req.args.get('current').strip().replace('\r', '')

            # encode to utf-8
            current = current.encode('utf-8')

            # parse and validate authz file with a config parser
            from ConfigParser import ConfigParser
            from StringIO import StringIO
            cp = ConfigParser()
            try:
                cp.readfp(StringIO(current))
            except Exception, e:
                raise TracError("Invalid Syntax: %s" % exception_to_unicode(e))

            # write to disk
            try:
                fp = open(authz_file, 'wb')
                current = fp.write(current)
                fp.close()
            except Exception, e:
                raise TracError("Can't write authz file: %s" % exception_to_unicode(e))

            add_notice(req, _('Your changes have been saved.'))
            req.redirect(req.panel_href())

        # read current authz file
        current = ""
        try:
            fp = open(authz_file,'r')
            current = fp.read()
            fp.close()
        except Exception, e:
            add_warning(req, 'Error occurred while reading authz file: %s' % exception_to_unicode(e))

        return 'svnauthz_raw.html', {'auth_data':current}

    def _do_htpasswd(self, req):
        if req.method == 'POST':
            username = req.args.get('username')
            if not username:
                add_warning(req, 'Username can not be empty')
            elif req.args.has_key('add'):
                password = req.args.get('password')
                if not password:
                    add_warning(req, 'Password can not be empty')
                else:
                    err = self.change_password(username, password)
            elif req.args.has_key('del'):
                err = self.delete_user(username)
            else:
                err = 'Unknown action'

            if not err:
                add_notice(req, _('Your changes have been saved.'))
                req.redirect(req.panel_href())
            else:
                add_warning(req, err)

        data = {
            'username': req.args.get('username'),
            'password': req.args.get('password'),
        }
        return 'svn_htpasswd.html', data

    def _check_dir(self, req, dir):
        """Check that a repository directory is valid, and add a warning
        message if not.
        """
        if not os.path.isabs(dir):
            add_warning(req, _('The repository directory must be an absolute '
                               'path.'))
            return False
        prefixes = [os.path.join(self.env.path, prefix)
                    for prefix in self.allowed_repository_dir_prefixes]
        if prefixes and not any(is_path_below(dir, prefix)
                                for prefix in prefixes):
            add_warning(req, _('The repository directory must be located '
                               'below one of the following directories: '
                               '%(dirs)s', dirs=', '.join(prefixes)))
            return False
        return True

    # Public API

    def change_password(self, username, password):
        '''Change SVN user password / Add new SVN user.
        Return None on success or error string on fail.
        Raise exception when configuration options are empty.'''

        try:
            args = (self.htpasswd, '-b', self.passwd_path, username, password)
            ret = subprocess.call(args)
        except Exception, e:
            return ('Error occurred while calling htpasswd: %s' % exception_to_unicode(e))

        if ret == 0:
            return  # success

        err = self._return_code_msg(ret)
        if err:
            return err

        return 'Error occurred while setting SVN password. Htpasswd returned %s.' % ret

    def delete_user(self, username):
        '''Delete SVN user.
        Return None on success or error string on fail.
        Do nothing (as success) if user doesn't exist.'''

        try:
            args = (self.htpasswd, '-D', self.passwd_path, username)
            ret = subprocess.call(args)
        except Exception, e:
            return ('Error occurred while calling htpasswd: %s' % exception_to_unicode(e))

        if ret == 0:
            return  # success

        err = self._return_code_msg(ret)
        if err:
            return err

        # TODO: special cases for all return codes (see htpasswd(1) man)
        return 'Error occurred while deleting SVN user. Htpasswd returned %s.' % ret

    def _return_code_msg(self, ret):
        '''Return error string for known error codes
        or None for unknown.'''
        # TODO: special cases for all return codes (see htpasswd(1) man)
        if ret == 1:
            return "Can't access SVN password file: %s" % self.passwd_path

    # ITemplateProvider methods
    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]
    
    def get_htdocs_dirs(self):
        """Return a list of directories with static resources (such as style
        sheets, images, etc.)
        """
        from pkg_resources import resource_filename
        return [('svnadmin', resource_filename(__name__, 'htdocs'))]