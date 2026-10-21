"""
Génération de PDF à partir de templates HTML avec WeasyPrint.
Couvre : facture de vente, ticket de caisse (format imprimante thermique),
et grand livre de stock.
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML


def render_pdf(template_name, context, filename, as_attachment=True):
    """Rend un template HTML en PDF et le renvoie en téléchargement direct.

    Fonctionne aussi bien sur mobile (navigateur) que sur desktop : le
    navigateur propose le téléchargement / l'ouverture du PDF automatiquement.
    """
    html_string = render_to_string(template_name, context)
    pdf_bytes = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    disposition = "attachment" if as_attachment else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response