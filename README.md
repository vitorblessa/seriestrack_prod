# 📺 SeriesTrack

**Acompanhe suas séries favoritas, nunca perca um episódio.**

SeriesTrack é um aplicativo web (e Android) para quem assiste séries de TV. Você monta sua biblioteca pessoal, recebe notificações push quando um novo episódio ou temporada estreia, sincroniza as datas de lançamento com o Google Calendar, pede recomendações a uma IA e acompanha suas estatísticas de consumo ao longo do ano.

🔗 **Produção:** [www.series-track.com](https://www.series-track.com)

---

## ✨ Funcionalidades

- **Biblioteca pessoal** — adicione séries (dados via [TMDB](https://www.themoviedb.org/)) com status *assistindo* / *quero assistir* / *concluído*, acompanhe progresso por episódio e deixe avaliações.
- **Notificações push (Web Push / VAPID)** — alerta automático diário de episódios estreando hoje/amanhã, com varredura resiliente mesmo em hospedagem com "cold start".
- **Sincronização com Google Calendar** — cria uma agenda separada ("SeriesTrack") na conta Google do usuário e mantém os próximos/últimos episódios de cada série atualizados automaticamente, todos os dias.
- **Feed iCal (.ics)** — alternativa sem OAuth: assine a agenda direto no Google Calendar, Apple Calendar ou qualquer app compatível.
- **Recomendações por IA** — sugestões de novas séries com base no histórico da biblioteca do usuário.
- **Stats avançadas & "Wrapped"** — um resumo anual, no estilo Spotify Wrapped, com os hábitos de maratona do usuário.
- **Login com Google (FedCM) ou e-mail/senha** — autenticação por JWT, com suporte a FedCM para evitar os bloqueios de pop-up/cookie de terceiros em navegadores modernos (Firefox, Chrome).
- **Assinatura Pro via Stripe** — upgrade com Checkout Sessions, webhook de confirmação e portal de cobrança, liberando biblioteca ilimitada e recursos extras.
- **Perfil público** — página compartilhável com as séries e avaliações do usuário.
- **App Android nativo (Capacitor)** — mesmo frontend web empacotado como app, publicado com Application ID `com.vitorblessa.seriestrack`.
- **Alta disponibilidade no plano gratuito** — um workflow do GitHub Actions mantém o backend "aquecido" (ping de login/logout a cada poucos minutos) e dispara de forma oportunista as varreduras diárias de notificação/sincronização, driblando o "sleep" de inatividade do Render free tier.

## 🏗️ Arquitetura

```
┌─────────────────┐       HTTPS        ┌──────────────────────┐
│  Frontend (SPA)  │ ─────────────────▶ │  Backend (FastAPI)   │
│  React 19 + CRA  │ ◀───────────────── │  Python 3.12          │
│  Tailwind CSS    │                    └──────────┬───────────┘
│  shadcn/radix-ui │                               │
│  hospedado no    │                               ├── MongoDB Atlas (Motor, async)
│  Vercel          │                               ├── TMDB API (catálogo de séries)
└──────────────────┘                               ├── Google Calendar API (OAuth, offline access)
        │                                            ├── Google Identity Services (login, FedCM)
        │ Capacitor                                  ├── Stripe (checkout + webhooks)
        ▼                                            └── Web Push (VAPID) via pywebpush
┌──────────────────┐
│   App Android    │       hospedado no Render (free tier)
│  (WebView + JS    │
│   empacotados)    │
└──────────────────┘
```

## 🛠️ Stack técnica

**Frontend** — `frontend/`
- React 19 + Create React App (CRACO)
- Tailwind CSS + componentes shadcn/ui (Radix UI)
- React Router 7, React Hook Form, Recharts (gráficos), Sonner (toasts)
- Capacitor 7 (`@capacitor/android`) para o build nativo Android

**Backend** — `backend/`
- FastAPI + Uvicorn
- MongoDB via Motor (driver assíncrono)
- APScheduler (varreduras diárias — notificações e sincronização de calendário)
- `pywebpush` (Web Push / VAPID), `google-api-python-client` (Calendar), `stripe` (cobrança)
- JWT (`PyJWT`) para autenticação por cookie/Bearer token

**Infra**
- Frontend: [Vercel](https://vercel.com)
- Backend: [Render](https://render.com) (plano free)
- Banco de dados: [MongoDB Atlas](https://www.mongodb.com/atlas)
- Keep-alive / cron oportunista: [GitHub Actions](https://github.com/features/actions) (`.github/workflows/`)

## 📂 Estrutura do repositório

```
backend/
  core/         # config, auth/JWT, conexão com Mongo, integrações (TMDB, Google Calendar), cron
  routes/       # endpoints FastAPI (auth, library, billing, push, calendar, ai, wrapped, ...)
  server.py     # ponto de entrada da API
  requirements.txt

frontend/
  src/
    pages/      # telas da aplicação (Dashboard, Biblioteca, Calendário, Stats, Wrapped, ...)
    components/ # componentes reutilizáveis + shadcn/ui
    lib/        # client HTTP (axios), auth context, helpers
  capacitor.config.ts   # configuração do build Android

scripts/
  keepalive_login.py    # ciclo de login/logout usado pelo keep-alive

.github/workflows/      # GitHub Actions (keep-alive do backend + ping dos crons diários)
render.yaml              # Blueprint de deploy do backend no Render
DEPLOY.md                 # guia passo a passo de deploy/configuração (produção)
```

## 🚀 Rodando localmente

### Pré-requisitos
- Node.js 18+ e Yarn/npm
- Python 3.12
- Uma instância MongoDB (local ou Atlas)
- Uma API Read Access Token do [TMDB](https://www.themoviedb.org/settings/api)

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # preencha MONGO_URL, TMDB_READ_TOKEN, JWT_SECRET, etc.
uvicorn server:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env   # REACT_APP_BACKEND_URL=http://localhost:8000
npm start
```

A aplicação sobe em `http://localhost:3000`, consumindo a API em `http://localhost:8000`.

### Variáveis de ambiente

As principais variáveis (backend) estão listadas em `render.yaml` e `backend/.env.example`, incluindo:

| Variável | Descrição |
|---|---|
| `MONGO_URL`, `DB_NAME` | Conexão com o MongoDB |
| `JWT_SECRET` | Chave de assinatura dos tokens de autenticação |
| `TMDB_READ_TOKEN` | Token da API do TMDB |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Login com Google + integração Google Calendar |
| `GOOGLE_CALENDAR_REDIRECT_URI` | Redirect URI do fluxo OAuth do Calendar |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` | Cobrança do plano Pro |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_PEM_PATH` / `VAPID_SUBJECT` | Notificações Web Push |
| `GEMINI_API_KEY` | Recomendações por IA |
| `CRON_SECRET` | Autoriza o ping externo das varreduras diárias (`POST /push/cron/ping`) |
| `PRO_OWNERS` | E-mails com Pro vitalício automático (uso interno/admin) |

Veja **[DEPLOY.md](./DEPLOY.md)** para o passo a passo completo de deploy em produção (Render + Vercel + MongoDB Atlas + Google Cloud Console + Stripe Dashboard).

## 🔄 Jobs em segundo plano

O backend roda duas varreduras diárias via APScheduler, ambas idempotentes (rodam no máximo uma vez por dia, mesmo se chamadas repetidamente):

| Job | Horário (UTC) | O que faz |
|---|---|---|
| `daily_push` | 12:00 | Notifica (push) usuários sobre episódios estreando hoje/amanhã nas séries da biblioteca |
| `daily_calendar_sync` | 12:30 | Resincroniza o Google Calendar de todo usuário conectado, mantendo os próximos episódios sempre atualizados |

Como o backend roda no plano gratuito do Render (que "dorme" após ~15 min de inatividade), um workflow do GitHub Actions (`.github/workflows/keepalive.yml`) faz um ciclo real de login/logout a cada poucos minutos — isso mantém o processo acordado e, via `POST /push/cron/ping` (protegido por `CRON_SECRET`), dispara essas varreduras oportunamente caso o horário exato tenha sido perdido com o serviço dormindo.

## 📱 App Android

O app Android é o mesmo frontend web empacotado via [Capacitor](https://capacitorjs.com/), sem depender do domínio do site — apenas da API (`REACT_APP_BACKEND_URL`). Para gerar o build:

```bash
cd frontend
npm run build
npx cap sync android
npx cap open android   # abre no Android Studio
```

## 📄 Licença

Projeto privado — todos os direitos reservados.
