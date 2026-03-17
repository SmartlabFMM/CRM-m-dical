from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

class SmartLabHome(Home):
    @http.route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        # Call the original method to handle all the login logic (validation, session, etc.)
        response = super(SmartLabHome, self).web_login(redirect=redirect, **kw)
        
        # If the response is a rendering of the login page (not a redirect)
        if hasattr(response, 'qcontext') and response.is_qweb:
            # Check if this is a GET request or a POST request that failed
            # Render our custom SmartLab login template instead of the default one
            response.template = 'smartlab.smartlab_login'
            
        return response
