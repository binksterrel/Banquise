"""
Génère le PDF des APIs & IA avec la charte Banquise (dégradés, cartes glassy).
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors


def generate_pdf(output_path: Path):
    # Palette Banquise
    ice50 = colors.HexColor("#f0f9ff")
    ice100 = colors.HexColor("#e0f2fe")
    ice500 = colors.HexColor("#0ea5e9")
    blue600 = colors.HexColor("#2563eb")
    ink = colors.HexColor("#0f172a")
    slate500 = colors.HexColor("#64748b")
    slate200 = colors.HexColor("#e2e8f0")
    slate100 = colors.HexColor("#f1f5f9")
    emerald500 = colors.HexColor("#10b981")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    w, h = A4
    c.setTitle("Banquise - APIs & IA")

    # Fond dégradé doux
    c.setFillColor(ice50)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(ice100)
    c.rect(0, h * 0.55, w, h * 0.45, fill=1, stroke=0)
    c.setFillColor(ice500)
    c.setStrokeColor(ice500)
    c.setLineWidth(0)
    c.circle(w * 0.85, h * 0.85, 120, fill=1, stroke=0)
    c.setFillColor(blue600)
    c.circle(w * 0.15, h * 0.15, 90, fill=1, stroke=0)

    # Header card
    c.setFillColor(colors.white)
    c.setStrokeColor(slate200)
    c.setLineWidth(1)
    c.roundRect(28, h - 170, w - 56, 140, 18, fill=1, stroke=1)
    c.setFillColor(ice500)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, h - 60, "APIs • Scoring Crédit • Notifications")
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, h - 95, "Banquise — APIs & IA")
    c.setFillColor(slate500)
    c.setFont("Helvetica", 11)
    c.drawString(50, h - 115, "Vue synthétique des endpoints, du scoring (métier + ML) et du flux de validation.")

    # Utilitaire carte
    def card(title, lines, y, badge=None):
        margin = 40
        line_height = 13
        height = 54 + line_height * len(lines)
        # Si pas assez de place, nouvelle page
        if y - height < 60:
            c.showPage()
            # Redessiner un fond léger sur nouvelle page
            c.setFillColor(ice50)
            c.rect(0, 0, w, h, fill=1, stroke=0)
            c.setFillColor(ice100)
            c.rect(0, h * 0.55, w, h * 0.45, fill=1, stroke=0)
            y = h - 40

        c.setFillColor(colors.white)
        c.setStrokeColor(slate200)
        c.setLineWidth(1)
        c.roundRect(margin, y - height, w - 2 * margin, height, 14, fill=1, stroke=1)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 12.5)
        c.drawString(margin + 14, y - 22, title)
        if badge:
            c.setFillColor(ice500)
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(w - margin - 10, y - 22, badge)
        c.setFont("Helvetica", 10.5)
        c.setFillColor(slate500)
        ty = y - 40
        for line in lines:
            c.drawString(margin + 14, ty, line)
            ty -= line_height
        return y - height - 16

    sections = [
        ("Comptes & Paiements", [
            "POST /virement/ — exécuter un virement interne",
            "POST /beneficiaires/ — ajouter un bénéficiaire",
            "GET  /releve-compte/<id>/ — récupérer un relevé",
            "GET  /rib-compte/<id>/pdf/ — générer un RIB PDF"
        ], "Banking"),
        ("Cartes & Sécurité", [
            "GET  /cartes/ — lister les cartes",
            "POST /gestion-plafonds/<id>/ — ajuster les plafonds",
            "POST /console/manage/ (admin) — bloquer/débloquer une carte"
        ], "Cards"),
        ("Crédit & Découvert", [
            "POST /simulation/ — calcul score + brouillon",
            "GET  /resultat/<id>/ — afficher/ajuster",
            "POST /api/resultat/<id>/update/ — ajuster durée/mensualité",
            "POST /resultat/<id>/valider/ — envoi aux conseillers",
            "GET  /historique/ — historique des demandes",
            "POST /demande-decouvert/ — relèvement temporaire"
        ], "Loans"),
        ("Notifications & Emails", [
            "send_mail (Mailtrap) pour codes et alertes",
            "Notifications internes (CREDIT, INFO, etc.)",
            "Pas de notif aux conseillers tant que l'utilisateur n'a pas validé"
        ], "Notify"),
        ("Admin & Observabilité", [
            "/admin-dashboard/ — stats",
            "/console/credits/ — validation crédits",
            "/console/manage/ — gestion comptes/cartes/bénéficiaires",
            "/admin/ — back-office"
        ], "Admin"),
        ("Scoring IA (métier + ML)", [
            "Features : revenus, DTI, LTV, apport, emploi (bonus CDI), logement (bonus proprio), santé",
            "Heuristique : pénalités DTI/LTV assouplies, bonus apport/emploi/logement",
            "ML : régression logistique sur dataset synthétique (600 profils)",
            "Score final = moyenne (heuristique + ML), seuil acceptation ≥ 55",
            "Notifications seulement après clic \"Valider et envoyer\""
        ], "AI"),
        ("IA — Exemple explicite", [
            "Revenus 4 500 €, charges/dettes 900 € → DTI ~20 %",
            "Prêt 150 000 €, apport 15 000 € → LTV ~90 %",
            "CDI, propriétaire : bonus stabilité",
            "Score final > 55 → avis auto favorable si l'utilisateur valide"
        ], "Exemple"),
        ("Exemple rapide", [
            "Revenus 4 500 €, charges/dettes 900 € → DTI ~20 %",
            "Prêt 150 000 €, apport 15 000 € → LTV ~90 %",
            "CDI, propriétaire : bonus stabilité",
            "Score final > 55 → avis auto favorable si l'utilisateur valide"
        ], "Exemple bis"),
        ("Limites / à prévoir", [
            "Modèle synthétique (pas de données réelles), pas de drift monitoring",
            "Pas de persistance modèle : recalcul à chaud en mémoire",
            "Pour la prod : dataset réel, consentement, supervision humaine"
        ], "Warning"),
    ]

    y = h - 190
    for title, lines, badge in sections:
        y = card(title, lines, y, badge=badge)

    # Footer
    c.setFillColor(slate500)
    c.setFont("Helvetica", 9)
    c.drawString(40, 30, "Banquise • APIs & IA • https://banquise.com")

    c.showPage()
    c.save()


if __name__ == "__main__":
    generate_pdf(Path("scoring/static/docs/banquise_apis.pdf"))
