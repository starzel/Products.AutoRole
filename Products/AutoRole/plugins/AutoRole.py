import socket
import struct
import logging

from zope.event import notify
from Products.AutoRole.interfaces import ConfigurationChangedEvent

from AccessControl.SecurityInfo import ClassSecurityInfo
from Globals import InitializeClass
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from Products.PluggableAuthService.utils import classImplements
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.interfaces.plugins import IRolesPlugin
from Products.PluggableAuthService.interfaces.plugins import IGroupsPlugin
from Products.PluggableAuthService.interfaces.plugins import IExtractionPlugin
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin

try:
    set
except NameError:
    # Python 2.3
    from sets import Set as set

log = logging.getLogger(__name__)

manage_addAutoRoleForm = PageTemplateFile(
    'www/autoRoleAdd', globals(), __name__='manage_addAutoRoleForm')


def addAutoRole( dispatcher
               , id
               , title=None
               , ip_roles=()
               , REQUEST=None
               ):
    """ Add an AutoRole plugin to a Pluggable Auth Service. """
    sp = AutoRole(id, title, ip_roles)
    dispatcher._setObject(sp.getId(), sp)

    if REQUEST is not None:
        REQUEST['RESPONSE'].redirect( '%s/manage_workspace'
                                      '?manage_tabs_message='
                                      'AutoRole+added.'
                                    % dispatcher.absolute_url() )

def quad2int(ip):
    "Convert an IP address in dotted quad notation to base10 integer"
    try:
        return struct.unpack('!L', socket.inet_aton(ip))[0]
    except (TypeError, socket.error):
        return 0


class AutoRole(BasePlugin):
    """ Multi-plugin for assigning auto roles from IP. """

    meta_type = 'Auto Role Plugin'
    security = ClassSecurityInfo()

    _properties = (
        dict(id='title', label='Title', type='string', mode='w'),
        dict(id='ip_roles', label='IP filter and roles', type='lines',
             mode='w'),
        dict(id='anon_only', label='Anonymous Only', type='boolean',
             mode='w'),
    )

    anon_only = False

    def __init__(self, id, title=None, ip_roles=()):
        self._setId(id)
        self.title = title
        self.ip_roles = ip_roles
        self.anon_only = False

    def _find_ip(self, request=None):
        """ Extract the client IP address from the HTTP request
        in a proxy-compatible way.

        @return: IP address as a string or None if not available
        """
        if request is None:
            request = getattr(self, 'REQUEST', None)
        if request is None:
            return None
        if "HTTP_X_FORWARDED_FOR" in request.environ:
            # Virtual host
            ip = request.environ["HTTP_X_FORWARDED_FOR"]
        elif "HTTP_HOST" in request.environ:
            # Non-virtualhost
            ip = request.environ["REMOTE_ADDR"]
        else:
            # Unit test code?
            ip = None
        log.debug('request.getClientAddr(): {0}'.format(
            request.getClientAddr()))
        log.debug('HTTP_X_FORWARDED_FOR: {0}'.format(
            request.get('HTTP_X_FORWARDED_FOR')))
        log.debug('REMOTE_ADDR: {0}'.format(request.get('REMOTE_ADDR')))
        return ip

    def _compile_subnets(self):
        self._compiled = compiled = []
        for line in self.ip_roles:
            try:
                subnet, roles = line.split(':')
                roles = [r.strip() for r in roles.split(',')]
                roles = set(filter(None, roles))
                if not roles:
                    continue
            except (ValueError, AttributeError):
                continue
            if not subnet:
                # No ip specification
                continue
            if '/' in subnet:
                subnet, bits = subnet.split('/')
                bits = int(bits)
                if 0 >= bits > 32:
                    continue
            else:
                # No mask, assume 32 bits
                bits = 32
            mask = (2 ** bits - 1) << (32 - bits)
            subnet = quad2int(subnet) & mask
            compiled.append((subnet, mask, roles))

    def _setPropValue(self, id, value):
        BasePlugin._setPropValue(self, id, value)
        if id == 'ip_roles':
            self._compile_subnets()
            if value and len(self._compiled) != len(self.ip_roles):
                raise ValueError(
                    'ip_roles contains invalid subnets and/or roles!')
            notify(ConfigurationChangedEvent(self))

    #
    # IRolesPlugin
    #
    security.declarePrivate('getRolesForPrincipal')
    def getRolesForPrincipal(self, principal, request=None):
        """ Assign roles based on 'request'. """
        if (self.anon_only and
                principal is not None and
                principal.getUserName() != 'Anonymous User'):
            return []
        if not getattr(self, '_compiled', None):
            self._compile_subnets()
        if not self._compiled:
            return []

        ip = quad2int(self._find_ip(request))
        if not ip:
            return []

        result = set()
        for subnet, mask, roles in self._compiled:
            if ip & mask == subnet:
                result.update(roles)
        return list(result)

    #
    # IGroupsPlugin
    #
    # This method allows the plugin to be used to assign groups instead of
    # roles if used as a group plugin instead of a role plugin.
    security.declarePrivate('getGroupsForPrincipal')
    def getGroupsForPrincipal(self, principal, request=None):
        """ Assign groups based on 'request'. """
        return self.getRolesForPrincipal(principal, request)

    #
    # IExtractionPlugin
    #
    security.declarePrivate('extractCredentials')
    def extractCredentials(self, request):
        # Avoid creating anon user if this is a regular user
        # We actually have to poke request ourselves to avoid users from
        # root becoming anonymous...
        if getattr(request, '_auth', None):
            return {}

        if not getattr(self, '_compiled', None):
            self._compile_subnets()
        if not self._compiled:
            return {}

        # get client IP
        ip = quad2int(self._find_ip(request))
        if not ip:
            return {}

        for subnet, mask, roles in self._compiled:
            if ip & mask == subnet:
                return dict(AutoRole=True)

        return {}

    #
    # IAuthenticationPlugin
    #
    security.declarePrivate('authenticateCredentials')
    def authenticateCredentials(self, credentials):
        if credentials.get('login'):
            return None
        autorole = credentials.get('AutoRole', None)
        if not autorole:
            return None
        return ('Anonymous User', 'Anonymous User')


classImplements( AutoRole
               , IRolesPlugin
               , IGroupsPlugin
               , IExtractionPlugin
               , IAuthenticationPlugin
               )

InitializeClass(AutoRole)
