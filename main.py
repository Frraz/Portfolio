"""
main.py - Aplicação FastAPI do Portfólio
"""

import os
import re
import ssl
import smtplib
import logging
from email.message import EmailMessage
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# =========================================================
# Logging
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("portfolio")

# =========================================================
# Variáveis de ambiente
# =========================================================
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "").strip()

# Domínios permitidos para CORS separados por vírgula em ALLOWED_ORIGINS
RAW_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1")
ALLOWED_ORIGINS = [o.strip() for o in RAW_ALLOWED_ORIGINS.split(",") if o.strip()]

# Se quiser liberar tudo temporariamente (NÃO recomendável em produção):
ALLOW_ALL_CORS = os.getenv("ALLOW_ALL_CORS", "false").lower() == "true"

# =========================================================
# App FastAPI
# =========================================================
app = FastAPI(
    title="Portfólio",
    description="API do Portfólio pessoal",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =========================================================
# CORS
# =========================================================
if ALLOW_ALL_CORS:
    logger.warning("CORS aberto (allow_origins=['*']). Ajuste ALLOW_ALL_CORS para 'false' em produção.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.info(f"CORS restrito às origens: {ALLOWED_ORIGINS}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
        allow_headers=["*"],
    )

# =========================================================
# ThreadPool para não bloquear loop com SMTP (opcional)
# Desative se quiser enviar direto: def send_email(...)
# =========================================================
EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv("SMTP_WORKERS", "3")))

# =========================================================
# Utilidades
# =========================================================
EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

def is_valid_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))

def missing_envs() -> list[str]:
    missing = []
    if not EMAIL_SENDER:
        missing.append("EMAIL_SENDER")
    if not EMAIL_PASSWORD:
        missing.append("EMAIL_PASSWORD")
    if not EMAIL_RECEIVER:
        missing.append("EMAIL_RECEIVER")
    return missing

def build_email(nome: str, email: str, mensagem: str) -> EmailMessage:
    subject = f"[Portfólio] Contato de {nome}"
    body = (
        "Você recebeu uma nova mensagem pelo portfólio:\n\n"
        f"Nome: {nome}\n"
        f"E-mail: {email}\n\n"
        f"Mensagem:\n{mensagem}\n"
    )
    em = EmailMessage()
    em["From"] = EMAIL_SENDER
    em["To"] = EMAIL_RECEIVER
    em["Subject"] = subject
    em.set_content(body)
    return em

def send_email_sync(em: EmailMessage) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(em)

async def send_email(em: EmailMessage) -> None:
    """
    Envia e-mail usando ThreadPool para não bloquear.
    """
    try:
        await app.loop.run_in_executor(EXECUTOR, send_email_sync, em)
    except Exception as e:
        logger.exception("Falha ao enviar e-mail.")
        raise HTTPException(status_code=500, detail="Erro ao enviar mensagem, tente novamente mais tarde.")

def validate_contact_fields(data: Dict[str, Any]) -> Dict[str, str]:
    nome = (data.get("nome") or "").strip()
    email = (data.get("email") or "").strip()
    mensagem = (data.get("mensagem") or "").strip()

    if not nome or not email or not mensagem:
        raise HTTPException(status_code=400, detail="Por favor, preencha todos os campos.")
    if len(nome) > 80:
        raise HTTPException(status_code=400, detail="Nome muito longo.")
    if len(email) > 120:
        raise HTTPException(status_code=400, detail="Email muito longo.")
    if len(mensagem) > 5000:
        raise HTTPException(status_code=400, detail="Mensagem muito longa.")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Por favor, insira um e-mail válido.")

    return {"nome": nome, "email": email, "mensagem": mensagem}

# =========================================================
# Rotas
# =========================================================
@app.get("/", response_class=HTMLResponse, tags=["pages"])
async def home(request: Request):
    """
    Página inicial do portfólio renderizada via template.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.head("/", tags=["pages"])
async def home_head():
    """
    Resposta simples para HEAD (monitoramentos / health checks).
    """
    return PlainTextResponse("", status_code=200)

@app.get("/healthz", tags=["infra"])
async def healthz():
    """
    Health check simples para monitoramento externo.
    """
    env_missing = missing_envs()
    return {
        "status": "ok",
        "missing_envs": env_missing,
        "app_version": "1.0.0"
    }

@app.post("/contato/", tags=["forms"])
async def contato(request: Request):
    """
    Recebe dados do formulário de contato e envia e-mail.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido.")

    campos = validate_contact_fields(data)

    env_missing = missing_envs()
    if env_missing:
        logger.error("Variáveis de ambiente faltando: %s", env_missing)
        raise HTTPException(
            status_code=500,
            detail=f"Erro de configuração: faltando {', '.join(env_missing)}"
        )

    em = build_email(campos["nome"], campos["email"], campos["mensagem"])
    await send_email(em)

    return JSONResponse({"msg": "Mensagem enviada com sucesso!"})

# =========================================================
# Eventos
# =========================================================
@app.on_event("startup")
async def on_startup():
    logger.info("Aplicação iniciando...")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Aplicação encerrando...")
    try:
        EXECUTOR.shutdown(wait=False)
    except Exception:
        pass