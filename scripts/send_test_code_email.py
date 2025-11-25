"""
Envoi d'un email de test avec un code fictif pour vérifier le template HTML Banquise.
Usage :
    source venv/bin/activate
    python manage.py shell -c "exec(open('scripts/send_test_code_email.py').read())"
"""

from django.core.mail import send_mail

code = "123456"  # code fictif
subject = "Banquise - Code de confirmation (test)"
recipient = "test@example.com"

html_message = f"""
<div style="background:#f8fafc;padding:32px;font-family:'Plus Jakarta Sans',Arial,sans-serif;color:#0f172a;">
  <div style="max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:24px;overflow:hidden;background:white;box-shadow:0 18px 45px rgba(8,47,73,0.15);">
    <div style="padding:22px 24px;background:linear-gradient(135deg,#0ea5e9,#6366f1);color:white;display:flex;align-items:center;justify-content:space-between;gap:12px;">
      <div style="display:flex;align-items:center;gap:12px;font-weight:800;font-size:19px;letter-spacing:0.6px;">
        <span style="display:inline-flex;width:42px;height:42px;border-radius:14px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);align-items:center;justify-content:center;font-size:20px;color:white;">❄️</span>
        <span style="text-transform:uppercase;color:white;">BANQUISE</span>
      </div>
      <span style="padding:8px 12px;border-radius:999px;border:1px solid rgba(255,255,255,0.4);font-weight:700;font-size:12px;letter-spacing:0.1em;">Sécurité</span>
    </div>
    <div style="padding:28px;">
      <p style="font-size:14px;font-weight:700;color:#0ea5e9;margin:0 0 6px;letter-spacing:0.08em;text-transform:uppercase;">Code de confirmation</p>
      <h2 style="margin:0 0 12px;font-size:24px;font-weight:800;color:#0f172a;line-height:1.3;">Activez votre compte Banquise</h2>
      <p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Bonjour Demo, voici votre code de vérification pour sécuriser votre inscription.</p>
      <div style="text-align:center;margin:26px 0;">
        <span style="display:inline-block;font-size:30px;font-weight:800;letter-spacing:10px;padding:18px 26px;border-radius:18px;background:#e0f2fe;color:#0ea5e9;border:1px solid #bae6fd;box-shadow:0 12px 25px rgba(14,165,233,0.18);">{code}</span>
      </div>
      <p style="font-size:13px;line-height:1.6;margin:0 0 14px;color:#475569;text-align:center;">Valide pendant 10 minutes. Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>
      <div style="margin-top:22px;padding:16px 18px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0;display:flex;gap:12px;align-items:flex-start;">
        <span style="width:34px;height:34px;border-radius:10px;background:#e0f2fe;color:#0ea5e9;display:inline-flex;align-items:center;justify-content:center;font-weight:800;">i</span>
        <div>
          <p style="margin:0;font-size:12px;font-weight:800;color:#0ea5e9;letter-spacing:0.08em;text-transform:uppercase;">Support Banquise</p>
          <p style="margin:4px 0 0;font-size:13px;color:#475569;">Besoin d'aide ? Répondez à cet email ou ouvrez le chat support depuis l'app.</p>
        </div>
      </div>
    </div>
    <div style="background:#0f172a;color:white;padding:14px 24px;font-size:12px;text-align:center;letter-spacing:0.04em;">
      Banquise • Banque nouvelle génération • www.banquise.com
    </div>
  </div>
</div>
"""

plain_message = f"Code: {code}"

sent = send_mail(
    subject,
    plain_message,
    "no-reply@banquise.demo",
    [recipient],
    fail_silently=False,
    html_message=html_message
)

print(f"Email de test envoyé ? {bool(sent)} (sent={sent})")
