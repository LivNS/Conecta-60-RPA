# Publicar o MVP em uma URL pública (provisória, gratuita)

Tempo estimado: 20 a 30 minutos. Não precisa de cartão de crédito.

## 1. Repositório no GitHub

1. Em github.com, clique em **New repository**. Escolha um nome (ex.: `conecta60`), marque **Public** e crie **sem** README.
2. Envie o conteúdo do `projeto-gs.zip` (descompactado). O jeito mais seguro, porque a pasta `.github` começa com ponto e alguns sistemas a escondem no arrastar-e-soltar:

```bash
cd pasta-descompactada
git init && git add . && git commit -m "MVP: alertas + robô RPA"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/conecta60.git
git push -u origin main
```

Confira no GitHub que aparecem `app/`, `rpa/`, `render.yaml` e `.github/workflows/`.

## 2. Publicar no Render

1. Em render.com, entre com a conta do GitHub.
2. **New → Blueprint** e escolha o repositório. O Render lê o `render.yaml` e mostra o serviço `conecta60-mvp`. Clique em **Apply**.
3. Espere a primeira publicação (alguns minutos). A URL aparece no topo do serviço, algo como `https://conecta60-mvp.onrender.com`.
4. Teste: abra `/alertas` (4 alertas de demonstração) e `/saude`.
5. Em **Environment**, copie os valores gerados de `ADMIN_SENHA` (login da tela `/revisao`, usuário `revisor`) e `RPA_API_TOKEN`.

## 3. Ligar o robô ao MVP publicado

No repositório do GitHub: **Settings → Secrets and variables → Actions**.

| Tipo | Nome | Valor |
| --- | --- | --- |
| Secret | `RPA_API_URL` | URL do Render, sem barra no final |
| Secret | `RPA_API_TOKEN` | Valor copiado do Render |
| Variable | `MVP_URL` | A mesma URL (ativa o "despertador") |

Depois: **Actions → RPA - alertas de golpes → Run workflow**. Ao terminar, abra `/revisao` no MVP: as notícias reais de golpe da Agência Brasil chegam como rascunhos. Os logs ficam no próprio run do Actions, em **Artifacts**.

## Limites do plano gratuito (diga isso na apresentação, se perguntarem)

- O serviço adormece após 15 minutos sem acesso e leva cerca de 1 minuto para acordar. O workflow **Manter MVP acordado** acessa `/saude` a cada 10 minutos; ainda assim, abra a URL 1 minuto antes de gravar.
- O disco é apagado quando o serviço reinicia. Os 4 alertas de demonstração voltam sozinhos; rascunhos pendentes e aprovações feitas depois se perdem. Para guardar tudo, o colega de DevOps pode trocar por um banco gerenciado na nuvem da disciplina dele (a mesma imagem Docker serve).
- Esta publicação é provisória. A disciplina de DevOps exige Terraform, pipeline com Gitleaks/Semgrep/Trivy e monitoramento: isso continua com o colega, usando o mesmo `app/Dockerfile`.
