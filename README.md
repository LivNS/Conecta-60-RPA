# Conecta 60+ (nome provisório)

CitizenTech da Global Solution FIAP 2026.2 · Engenharia de Software 4º ano. Um único produto atravessa as sete disciplinas.

## Ficha Técnica do MVP

| Item | Conteúdo |
| --- | --- |
| Nome do produto | Conecta 60+ _(nome final a confirmar)_ |
| Cidadão e território | Pessoas com 60 anos ou mais que usam celular, WhatsApp e app de banco, em cidades e no campo |
| Problema, em uma frase | A pessoa idosa entrou no mundo digital mais rápido do que aprendeu a se defender dele, e o golpe virou o crime patrimonial mais comum do país |
| Proposta de valor | Verificar uma mensagem suspeita, entender os sinais de golpe em linguagem simples e aprender a reconhecer a próxima; grátis para quem usa, pago por instituições |
| Arquitetura: componentes | App web FastAPI (alertas, revisão; verificador e trilha a seguir) · Robô RPA em Python · banco SQLite/PostgreSQL · _demais disciplinas: preencher_ |
| Fontes de dados | Feed RSS da Agência Brasil (real, filtrado por relevância) · boletins simulados documentados · _Big Data: preencher_ |
| Modelos de IA utilizados | _GenAI: preencher_ |
| URL do MVP e repositório | _preencher_ |
| Indicadores de impacto | Ganho de conhecimento (quiz final − pré-teste) · pessoas capacitadas · alertas publicados por semana · tempo entre coleta e aprovação |
| ODS conectados | ODS 10 (redução das desigualdades) · ODS 4 (educação de qualidade) · ODS 11 (cidades e comunidades sustentáveis) |

## Integrantes

| Nome completo | RM | Disciplinas |
| --- | --- | --- |
| _preencher_ | _preencher_ | RPA, BI & Startup Development |
| _preencher_ | _preencher_ | _preencher_ |
| _preencher_ | _preencher_ | _preencher_ |

## Estrutura

```
app/        MVP web (FastAPI): API de alertas, tela de revisão, página pública
rpa/        Robô de alertas de golpes (disciplina de RPA) — ver rpa/README.md
scripts/    integração de ponta a ponta robô + app, com prints
.github/    agendamento diário do robô e "despertador" do MVP (GitHub Actions)
render.yaml publicação provisória gratuita do MVP — passo a passo em PUBLICAR.md
```
