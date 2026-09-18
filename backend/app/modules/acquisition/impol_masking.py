"""Certificate masking bounded by OCR anchors, then by actual ink extents.

Only the recognised Impol certificate layout is supported. Unknown boundaries
stop before AI; original images are never modified. DDT masks are independent.
"""
import re

from fastapi import HTTPException
from PIL import ImageDraw


class ImpolMaskReviewRequired(HTTPException):
    def __init__(self, reason):
        super().__init__(409, f"Mascheramento certificato Impol da verificare: {reason}. Nessuna immagine inviata all'AI.")


def token(word):
    return re.sub(r"[^A-Z0-9]", "", str(word.get("text", "")).upper())


def mask_certificate(image, words):
    masked = image.convert("RGB").copy()
    w, h = masked.size
    pad = max(2, round(w / 400))
    if not words:
        raise ImpolMaskReviewRequired("OCR non disponibile")
    title = [v for v in words if token(v) in {"INSPECTION", "CERTIFICATE"} and v["top"] < h * .14]
    orders = [v for v in words if token(v) in {"CUSTOMER", "SUPPLIER"} and h * .18 < v["top"] < h * .29]
    if len(title) < 2 or len(orders) < 2:
        raise ImpolMaskReviewRequired("intestazione o confine dei campi ordine non riconosciuti")
    order_top = min(v["top"] for v in orders)
    number = [v for v in words if token(v) == "NO" and w * .32 < v["left"] < w * .58 and h * .025 < v["top"] < h * .14]
    customer_top = max((v["bottom"] for v in number), default=h * .10) + pad * 2
    if customer_top >= order_top - pad * 4:
        raise ImpolMaskReviewRequired("confini dell'intestazione sovrapposti")

    protected_terms = {"CUSTOMER", "SUPPLIER", "ORDER", "PACKING", "NETTO", "ISSUE", "PRODUCT", "CHEMICAL", "MECHANICAL"}
    protected = [v for v in words if token(v) in protected_terms and v["top"] >= order_top]

    def cover(box, *, protect=True):
        left, top, right, bottom = [round(x) for x in box]
        left, top, right, bottom = max(0,left), max(0,top), min(w,right), min(h,bottom)
        if right <= left or bottom <= top:
            return
        if protect and any(v["left"] < right and v["right"] > left and v["top"] < bottom and v["bottom"] > top for v in protected):
            raise ImpolMaskReviewRequired("zona riservata sovrapposta a un campo tecnico")
        # Find actual content rather than blacking out the entire search rectangle.
        ink = image.crop((left,top,right,bottom)).convert("L").point(lambda x: 255 if x < 235 else 0)
        bounds = ink.getbbox()
        if bounds:
            x0,y0,x1,y1 = bounds
            ImageDraw.Draw(masked).rectangle((max(left,left+x0-pad),max(top,top+y0-pad),
                                            min(right-1,left+x1+pad),min(bottom-1,top+y1+pad)),fill="black")

    # Search areas are limited by actual order labels; Supplier Order No. stays below.
    logo_top = min([h*.025] + [v["top"]-pad*2 for v in words if v["left"] > w*.64 and v["top"] < order_top])
    cover((w*.64, logo_top, w*.98, order_top-pad*2))
    cover((w*.025, customer_top, w*.60, order_top-pad*2))

    # Complete customer-name stamps outside the address block, including suffixes.
    for word in words:
        if "RGIALLUMINIO" not in token(word) or word["top"] < order_top:
            continue
        peers = [v for v in words if v["left"] >= word["left"]-pad and v["left"] < word["right"]+w*.15
                 and v["top"] < word["bottom"] and v["bottom"] > word["top"]]
        cover((word["left"]-pad*2, min(v["top"] for v in peers)-pad,
               max(v["right"] for v in peers)+pad*2, max(v["bottom"] for v in peers)+pad))

    # Signature panels have supplier seals and names not reliably readable by OCR.
    groups = [v for v in words if token(v) == "GROUP" and order_top < v["top"] < h*.85]
    if groups:
        start = min(v["top"] for v in groups)-pad*3
        end = start+h*.15
        conformity = [v for v in words if v["top"] > start and token(v) in {"ORGANIZATION", "HEREBY", "ISO", "REQUIREMENTS", "ORDER"}]
        if conformity:
            end = min(end, min(v["top"] for v in conformity)-pad*2)
        panel = [token(v) for v in words if start <= v["top"] < end]
        if "QUALITY" not in panel or "DIRECTOR" not in panel or any(t in panel for t in ("CHARGE", "CLASS", "ROHS", "HYDROGEN", "TESTED")):
            raise ImpolMaskReviewRequired("pannello firme non separabile dai dati tecnici")
        cover((w*.025,start,w*.68,end))

    # Legal company footer, while retaining ISO / order conformity and page number.
    footer = [v for v in words if v["top"] > h*.88 and (token(v).startswith(("DRU", "DAV")) or token(v) == "REGISTER")]
    if footer:
        footer_top = min(v["top"] for v in footer)-pad
        order_words = [v for v in words if v["top"] > h*.88 and token(v) in {"ORDER", "REQUIREMENTS", "SUPPLIED"}]
        footer_top = max(footer_top, max((v["bottom"] for v in order_words), default=0)+pad)
        tax_words = [v for v in footer if token(v).startswith("DAV")]
        if not tax_words:
            raise ImpolMaskReviewRequired("fine del blocco recapiti non riconosciuta")
        tax_top = min(v["top"] for v in tax_words)
        tax_line = [v for v in words if abs(v["top"]-tax_top) < h*.006]
        cover((w*.02,footer_top,w*.98,max(v["bottom"] for v in tax_line)+pad),protect=False)
    else:
        raise ImpolMaskReviewRequired("blocco societario a piè pagina non riconosciuto")
    # Local provenance only: never serialized into the AI prompt or image file.
    masked.info["impol_source_text"] = " ".join(str(v["text"]) for v in words)
    return masked
