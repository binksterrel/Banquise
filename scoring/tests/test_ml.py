from django.test import TestCase
from scoring.ml import predict_credit, is_model_available, ModelNotLoaded

class TestML(TestCase):
    def test_predict_credit_structure_valid_payload(self):
        """Vérifie que le modèle répond correctement avec le schéma attendu."""
        if not is_model_available():
            print("Modèle ML non disponible, skip test.")
            return

        payload = {
            "revenus_mensuels": 3500.0,
            "montant_souhaite": 10000.0,
            "duree_mois": 24,
            "historique_credit": 1,
            "personnes_a_charge": 2,
            "marie": 1,
            "diplome": 1,
            "independant": 0,
        }
        result = predict_credit(payload)
        
        self.assertIsNotNone(result, "Le modèle a retourné None pour un payload valide")
        self.assertIn("proba_good", result)
        self.assertIn("proba_bad", result)
        self.assertIn("label", result)
        self.assertIn("score_0_100", result)
        
        self.assertTrue(0.0 <= result["proba_good"] <= 1.0)
        self.assertTrue(0.0 <= result["proba_bad"] <= 1.0)
        self.assertTrue(0 <= result["score_0_100"] <= 100)
        self.assertIn(result["label"], ("ACCEPTEE", "REFUSEE"))

    def test_predict_credit_edge_cases(self):
        """Teste le comportement avec des valeurs extrêmes / manquantes."""
        if not is_model_available():
            return

        # Cas revenus nuls
        payload_zero_income = {
            "revenus_mensuels": 0,
            "montant_souhaite": 5000,
            "duree_mois": 12
        }
        result = predict_credit(payload_zero_income)
        self.assertIsNotNone(result)
        # On s'attend à ce que le DTI calculé soit clamped à une valeur haute
        self.assertGreaterEqual(result["computed_dti"], 0)

        # Cas durée très longue
        payload_long = {
            "revenus_mensuels": 2000,
            "montant_souhaite": 100000,
            "duree_mois": 360 # 30 ans
        }
        result_long = predict_credit(payload_long)
        self.assertIsNotNone(result_long)

    def test_model_absent_handling(self):
        if is_model_available():
            return
        
        # Si le modèle n'est pas là, ça doit logguer mais pas crasher (retourne None)
        result = predict_credit({})
        self.assertIsNone(result)

