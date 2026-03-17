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
        compute='_calculer_stock',
        store=True
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

    @api.depends()
    def _calculer_stock(self):
        """
        Ici vous pouvez calculer la quantité réelle selon vos mouvements internes
        pour l’instant on initialise à 0.0 par défaut.
        """
        for rec in self:
            rec.quantite_stock = 0.0

    def reapprovisionner(self):
        """
        Cette méthode peut être étendue pour créer des commandes internes
        de réapprovisionnement dans votre module SmartLab
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Réapprovisionnement',
            'res_model': 'stock.picking', 
            'view_mode': 'form',
        }

   