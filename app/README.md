# App (MVP) — módulo de alertas

Recebe os rascunhos do robô de RPA, oferece a tela de revisão humana e publica os alertas aprovados.

## Rodar

```bash
cd app
pip install -r requirements.txt
export RPA_API_TOKEN=troque ADMIN_USUARIO=revisor ADMIN_SENHA=troque
PYTHONPATH=src uvicorn app_alertas.main:app --port 8000
python -m pytest -q        # 11 testes
```

| Rota | Quem usa | O que faz |
| --- | --- | --- |
| `POST /api/alertas/rascunhos` | Robô (Bearer `RPA_API_TOKEN`) | 201 criado · 409 já existe · 401 token inválido · 422 formato inválido |
| `GET /revisao` | Revisor (login) | Lista pendentes; aprovar (escolhendo o tema, se faltar) ou rejeitar com motivo |
| `GET /alertas` | Cidadão | Só alertas aprovados, com letra grande e dicas de proteção |
| `GET /api/alertas` | Outros componentes | JSON dos alertas publicados |
| `GET /api/alertas/pendentes`, `POST /api/alertas/{id}/aprovar` e `/rejeitar` | Revisor (login) | Mesmas ações em JSON |
| `GET /saude` | Monitoramento | Status e contagem por situação |
| `GET /docs` | Equipe | Documentação automática da API |

Variáveis: `RPA_API_TOKEN`, `ADMIN_USUARIO`, `ADMIN_SENHA` (obrigatórias), `DATABASE_PATH` (padrão `dados/alertas.db`), `APP_NOME` (nome exibido), `DADOS_INICIAIS` (JSON com alertas de demonstração carregados só quando o banco está vazio; já definido no Dockerfile), `PORT` (definida pela plataforma).

Contêiner: `docker build -t app-alertas app && docker run -p 8000:8000 -e RPA_API_TOKEN=... -e ADMIN_USUARIO=... -e ADMIN_SENHA=... app-alertas`.

Publicação provisória gratuita no Render: ver [`../PUBLICAR.md`](../PUBLICAR.md) (usa o `render.yaml` da raiz).

Próximos módulos do MVP (verificador de mensagens, trilha de aprendizagem, página de impacto) entram neste mesmo app.
