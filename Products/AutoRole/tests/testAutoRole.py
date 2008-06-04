#
# AutoRoleTestCase AutoRole
#

import unittest
import UserDict

from Products.PluggableAuthService.tests.conformance \
     import IRolesPlugin_conformance

class FakeRequest(UserDict.UserDict):
    client_ip = ''
    _auth = None
    
    def getClientAddr(self):
        return self.client_ip
    

class TestAutoRole(unittest.TestCase, IRolesPlugin_conformance):

    def _getTargetClass(self):
        from Products.AutoRole.plugins.AutoRole \
            import AutoRole

        return AutoRole

    def _makeOne( self, id='test', *args, **kw ):
        return self._getTargetClass()( id=id, *args, **kw )

    def test_getRolesForPrincipal( self ):
        helper = self._makeOne()
        request = FakeRequest()

        helper._updateProperty('ip_roles', ['10.0.1.1/24:Manager,Member'])
        request.client_ip = '10.0.1.1'
        self.assertEqual( helper.getRolesForPrincipal( None, request ), ['Member','Manager'])

        helper._updateProperty('ip_roles', ['10.0.1.1/24:Manager',
                                            '10.0.1.1/16:Member'])
        request.client_ip = '10.0.255.0'
        self.assertEqual( helper.getRolesForPrincipal( None, request ), ['Member'])
        request.client_ip = '10.0.1.1'
        self.assertEqual( helper.getRolesForPrincipal( None, request ), ['Member','Manager'])

        # Test for invalid ip address
        helper._updateProperty('ip_roles', ['10.0.1.1/24:Manager',
                                         '10.0.1.1/16:Member'])
        request.client_ip = '999.0.255.1234'
        self.assertEqual( helper.getRolesForPrincipal( None, request ), [])
        request.client_ip = 'invalidip'
        self.assertEqual( helper.getRolesForPrincipal( None, request ), [])
        request.client_ip = None
        self.assertEqual( helper.getRolesForPrincipal( None, request ), [])

        # Test for invalid subnets
        request.client_ip = '10.0.255.0'
        helper._updateProperty('ip_roles', [])
        self.assertEqual( helper.getRolesForPrincipal( None, request ), [])
        self.assertRaises(ValueError, helper._updateProperty, 
                          'ip_roles', ['999.0.1.1/24:Manager',
                                       '10.0.1.1/16:',
                                       ':Manager',
                                       'invalidsubnet',
                                        None])

    def test_extractCredentials( self ):
        helper = self._makeOne()
        request = FakeRequest()

        helper._updateProperty('ip_roles', ['10.0.1.1/24:Manager,Member'])
        request.client_ip = '10.0.1.1'
        self.assertEqual(helper.extractCredentials( request ), {'AutoRole':True})

        request.client_ip = '10.1.0.0'
        self.assertEqual( helper.extractCredentials( request ), {})

        request._auth = 'Basic' # No extraction if already http auth
        request.client_ip = '10.0.1.1'
        self.assertEqual( helper.extractCredentials( request ), {})

    def test_extractInvalidCredentials( self ):
        helper = self._makeOne()
        request = FakeRequest()

        helper._updateProperty('ip_roles', ['10.0.1.1/24:Manager,Member'])

        request.client_ip = '10.1.0.0, 127.0.0.1'
        self.assertEqual( helper.extractCredentials( request ), {})

        request.client_ip = 'invalidip'
        self.assertEqual( helper.extractCredentials( request ), {})

        request.client_ip = None
        self.assertEqual( helper.extractCredentials( request ), {})

    def test_authenticateCredentials( self ):
        helper = self._makeOne()

        self.assertEqual( helper.authenticateCredentials( {} ), None)
        self.assertEqual( helper.authenticateCredentials( {'AutoRole':True} ), ('Anonymous User','Anonymous User'))
        # Make sure we don't instantiate anonymous if there are other credentials
        self.assertEqual( helper.authenticateCredentials( {'AutoRole':True, 'login':'user','password':'password'} ), None)
        

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestAutoRole))
    return suite
