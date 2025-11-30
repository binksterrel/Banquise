import pytest

from scoring.ml import predict_credit, is_model_available, ModelNotLoaded


@pytest.mark.skipif(not is_model_available(), reason="Modèle ML non disponible")
def test_predict_credit_structure():
    payload = {
        "age": 35,
        "MonthlyIncome": 2500,
        "DebtRatio": 0.3,
        "NumberOfDependents": 1,
    }
    result = predict_credit(payload)
    assert "proba_good" in result
    assert "proba_bad" in result
    assert "label" in result
    assert 0 <= result["proba_good"] <= 1
    assert 0 <= result["proba_bad"] <= 1
    assert result["label"] in ("ACCEPTEE", "REFUSEE")


def test_model_absent_handling():
    if is_model_available():
        pytest.skip("Modèle présent, pas de test d'absence.")
    with pytest.raises(ModelNotLoaded):
        predict_credit({})
