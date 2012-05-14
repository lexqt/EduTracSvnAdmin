from trac.core import Component, implements

from acct_mgr.api import IAccountChangeListener
from svnadmin.api import SvnAdmin



class AccountManagerToSVNReplication(Component):
    """
    This class implements AccountChangeListener for user data
    replication into SVN password file.
    """

    implements(IAccountChangeListener)

    def __init__(self):
        self.svnadmin = SvnAdmin(self.env)

    # IAccountChangeListener

    def user_created(self, user, password):
        """User created"""
        res = self.svnadmin.set_password(user, password)
        self.log.debug("AccountManagerToSVNReplication: user_created: %s, %s" % (user, res or 'OK'))
        return res

    def user_password_changed(self, user, password):
        """Password changed"""
        res = self.svnadmin.set_password(user, password)
        self.log.debug("AccountManagerToSVNReplication: user_password_changed: %s, %s" % (user, res or 'OK'))
        return res

    def user_deleted(self, user):
        """User deleted"""
        res = self.svnadmin.delete_user(user)
        self.log.debug("AccountManagerToSVNReplication: user_deleted: %s" % (user, res or 'OK'))
        return res

    def user_password_reset(self, user, email, password):
        """User password reset"""
        pass

    def user_email_verification_requested(self, user, token):
        """User verification requested"""
        pass

