from odoo import models, fields, api


class MedicalLocation(models.Model):
    _name = 'medical.location'
    _description = 'Emplacement des Médicaments'

    name = fields.Char(string='Nom de l’emplacement', required=True)
    description = fields.Text(string='Description')


class MedicalMedication(models.Model):
    _name = 'medical.medication'
    _description = 'Médicament'

    #  Attributs 
    nom = fields.Char(string='Nom', required=True)
    substance_active = fields.Char(string='Substance active')
    forme = fields.Selection([
        ('comprime', 'Comprimé'),
        ('sirop', 'Sirop'),
        ('injectable', 'Injectable'),
        ('pommade', 'Pommade'),
        ('capsule', 'Capsule'),
        ('autre', 'Autre'),
    ], string='Forme', required=True)

    # Stock
    quantite_stock = fields.Float(
        string='Quantité en stock',
        
    )
    quantite_min = fields.Float(
        string='Quantité minimale',
        default=10.0
    )

   
    id_emplacement = fields.Many2one(
        'medical.location',
        string='Emplacement pharmacie'
    )

    # Alerte de stock
    alerte_stock = fields.Boolean(
        string='Alerte stock bas',
        compute='_verifier_alerte',
        store=True
    )

    #  Méthodes 
    @api.depends('quantite_stock', 'quantite_min')
    def _verifier_alerte(self):
        for rec in self:
            rec.alerte_stock = rec.quantite_stock < rec.quantite_min

    