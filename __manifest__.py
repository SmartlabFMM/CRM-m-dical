{
    'name': 'SmartLab Medical Center',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Complete Medical Center Management System',
    'depends': ['base', 'mail', 'contacts'],
    'license': 'LGPL-3',
    'data': [
        'security/groups.xml', 
      'security/ir.model.access.csv',
    
        'views/specialty_views.xml',
        'views/doctor_views.xml',
        'views/patient_views.xml',
        'views/rendezvous.xml',
        'views/consultation.xml',
        'views/medication_views.xml',
        'views/facture_views.xml',
        'views/assurance_views.xml',
        'views/room_views.xml',
        'templates/login.xml',
        'views/menu_views.xml',

    ],
    'assets': {
    'web.assets_frontend': [
        'smartlab/static/src/scss/login.css', 
    ],
},
     'installable': True,
     'application': True,
    'description': """
        SmartLab Medical Center Management
        ===================================
        
        Features:
        ---------
        * Patient Management
        * Doctor Management with Specialties
        * Appointment Scheduling
        * Medical Consultations
        * Prescription Management
        * Stock Management (Medications)
        * Invoicing and Payments
        * Analytics and Dashboards
        
        Technical Info:
        ---------------
        * Odoo Version: 19.0
        * Author: kais dhouieb
       
    """,
     'author': 'kais dhouieb',
     
  
}