"""Gera o Relatório Técnico de RPA em PDF, na ordem pedida pelo enunciado da GS.

Uso (pasta rpa/):  python docs/relatorio/gerar_relatorio.py
Lê docs/relatorio/dados.json (integrantes, RM, links) e as evidências em assets/, docs/ e logs/amostras/.
Saída: docs/relatorio/Relatorio_RPA.pdf
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

RPA = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
DADOS = json.loads((AQUI / "dados.json").read_text(encoding="utf-8"))
CHROME = "/usr/bin/google-chrome"


def e(t) -> str:
    return html.escape(str(t))


def campo(valor: str, rotulo: str) -> str:
    return e(valor) if valor else f'<span class="falta">[{e(rotulo)}]</span>'


def img(nome: str, legenda: str, classe: str = "") -> str:
    caminho = (RPA / nome).resolve()
    return (f'<figure class="{classe}"><img src="{caminho.as_uri()}" alt="{e(legenda)}">'
            f'<figcaption>{e(legenda)}</figcaption></figure>')


def recorte(nome: str, altura: int) -> str:
    from PIL import Image
    im = Image.open(RPA / nome)
    destino = AQUI / "_tmp" / Path(nome).name
    destino.parent.mkdir(exist_ok=True)
    im.crop((0, 0, im.width, min(altura, im.height))).save(destino)
    return str(destino.relative_to(RPA))


def recorte_trecho(nome: str, _trecho: str) -> str:
    """Mostra a parte final da tela (o rascunho sem tema fica por último)."""
    from PIL import Image
    im = Image.open(RPA / nome)
    destino = AQUI / "_tmp" / Path(nome).name
    destino.parent.mkdir(exist_ok=True)
    topo = max(0, im.height - 1150)
    im.crop((0, topo, im.width, im.height)).save(destino)
    return str(destino.relative_to(RPA))


def amostra_log(arquivo_glob: str, n: int = 9) -> str:
    arq = sorted((RPA / "logs" / "amostras").glob(arquivo_glob))[0]
    linhas = arq.read_text(encoding="utf-8").splitlines()[:n]
    return "<pre class='log'>" + "\n".join(e(l) for l in linhas) + "</pre>"


def resumo_json(cenario: str) -> dict:
    arq = sorted((RPA / "evidencias" / cenario / "logs").glob("resumo_*.json"))[-1]
    return json.loads(arq.read_text(encoding="utf-8"))


def montar_html() -> str:
    p = DADOS["produto"] or "[NOME DO PRODUTO]"
    integrantes = "".join(
        f"<tr><td>{campo(i['nome'], 'nome completo')}</td><td>{campo(i['rm'], 'RM')}</td></tr>"
        for i in DADOS["integrantes"])
    r1, r3 = resumo_json("1_sucesso"), resumo_json("3_falha")
    integ = json.loads((RPA / "evidencias" / "4_integracao" / "relato_integracao.json").read_text())

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 14mm 15mm 16mm 15mm; }}
@page paisagem {{ size: A4 landscape; margin: 12mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 9.9pt; color: #1b2433; line-height: 1.4; }}
h1 {{ font-size: 20pt; margin: 0 0 4pt; color: #0b3d6e; }}
h2 {{ font-size: 13.5pt; color: #0b3d6e; border-bottom: 1.5pt solid #0b3d6e; padding-bottom: 2pt; margin: 13pt 0 6pt; page-break-after: avoid; }}
h3 {{ font-size: 11pt; margin: 10pt 0 4pt; page-break-after: avoid; }}
p {{ margin: 0 0 6pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 4pt 0 10pt; font-size: 9.4pt; page-break-inside: avoid; }}
th, td {{ border: 0.6pt solid #b8c2d1; padding: 3.5pt 5pt; text-align: left; vertical-align: top; }}
th {{ background: #e8eef6; }}
.capa {{ border-left: 6pt solid #0b3d6e; padding-left: 12pt; margin-bottom: 14pt; }}
.sub {{ color: #4a5568; font-size: 11pt; }}
.falta {{ background: #fff1a8; padding: 0 3pt; font-weight: bold; }}
figure {{ margin: 6pt 0 12pt; page-break-inside: avoid; text-align: center; }}
figure img {{ max-width: 100%; max-height: 205mm; border: 0.6pt solid #c5ccd6; }}
figure.media img {{ max-height: 120mm; }}
figure.pequena img {{ max-height: 95mm; }}
figcaption {{ font-size: 8.6pt; color: #4a5568; margin-top: 3pt; }}
.paisagem {{ page: paisagem; }}
.paisagem figure img {{ max-height: 165mm; }}
pre.log {{ font-family: "DejaVu Sans Mono", monospace; font-size: 6.9pt; background: #f4f6f9; border: 0.6pt solid #d3d9e2;
  padding: 6pt; white-space: pre-wrap; word-break: break-all; page-break-inside: avoid; }}
code {{ font-family: "DejaVu Sans Mono", monospace; font-size: 8.8pt; background: #f1f3f6; padding: 0 2pt; }}
.destaque {{ background: #eef6f0; border-left: 4pt solid #1d6b3a; padding: 6pt 9pt; margin: 6pt 0 10pt; }}
.quebra {{ page-break-before: always; }}
ul {{ margin: 2pt 0 8pt 14pt; padding: 0; }} li {{ margin: 1.5pt 0; }}
</style></head><body>

<div class="capa">
<h1>Relatório Técnico — Robotic Process Automation</h1>
<div class="sub">Global Solution 2026.2 · CitizenTech · Engenharia de Software 4º ano · Turma {campo(DADOS.get('turma',''), 'turma')}</div>
<div class="sub">Componente <b>Automação</b> do produto <b>{e(p)}</b> · Robô de alertas educativos sobre golpes digitais</div>
<div class="sub">Professores: Bruno Diniz e Cibele Ribeiro</div>
</div>

<h2>1. Integrantes</h2>
<table><tr><th>Nome completo</th><th style="width:28%">RM</th></tr>{integrantes}</table>

<h2>2. A CitizenTech e o problema resolvido</h2>
<p><b>{e(p)}</b> é uma plataforma de inclusão e segurança digital para pessoas com 60 anos ou mais. Ela ajuda a reconhecer mensagens fraudulentas, explica os sinais de golpe em linguagem simples e ensina a agir com segurança, sem infantilizar e sem substituir bancos ou autoridades.</p>
<p><b>Problema operacional que a automação resolve:</b> golpes novos surgem toda semana. Para manter a área de <i>Alertas</i> atualizada, alguém precisaria vasculhar fontes confiáveis, separar o que é golpe do que não é, conferir se o aviso já foi publicado, reescrever em linguagem simples e registrar o que fez. É um trabalho repetitivo, sujeito a esquecimento e a duplicidade, que hoje seria feito à mão.</p>

<h2>3. Objetivo da automação e benefício para o cidadão</h2>
<p><b>Objetivo:</b> executar, todos os dias e sem intervenção humana, a coleta, a validação, a deduplicação, a classificação e a preparação de alertas educativos, entregando-os ao MVP como <b>rascunhos pendentes de revisão</b>. A única etapa humana é a decisão de publicar, porque divulgar informação incorreta para pessoas idosas seria um risco.</p>
<p><b>Benefício para o cidadão:</b> a pessoa 60+ encontra avisos atuais, conferidos por uma pessoa, escritos de forma simples e sempre acompanhados de três atitudes práticas de proteção. Para a operação, o trabalho manual cai para um clique de aprovação por alerta, com rastreabilidade completa.</p>

<h2>4. Descrição do processo e desenho do fluxo</h2>
<ol>
<li><b>Gatilho:</b> agendamento diário às 06h17 (GitHub Actions) ou execução manual.</li>
<li><b>Entrada:</b> lista de fontes permitidas em <code>config/fontes.json</code>: um feed RSS público real (Agência Brasil, com filtro de relevância) e uma pasta de boletins JSON/CSV.</li>
<li><b>Reenvio:</b> rascunhos que ficaram na fila em execuções anteriores são reenviados primeiro.</li>
<li><b>Repetição sobre as fontes</b>, com coleta resiliente (timeout e até 3 tentativas).</li>
<li><b>Repetição sobre os itens:</b> validar → verificar relevância → deduplicar → classificar tema → montar rascunho → entregar ao MVP.</li>
<li><b>Revisão humana no MVP:</b> aprovar (publica em <i>Alertas</i>) ou rejeitar com motivo.</li>
<li><b>Saída:</b> rascunhos no MVP, logs JSONL de auditoria, resumo da execução e estado persistido.</li>
</ol>
<p>O fluxo em BPMN 2.0 está em <code>docs/fluxo-rpa-alertas.bpmn</code> (abre no bpmn.io e no Camunda Modeler) e na próxima página (Figura 1).</p>



<h2 class="quebra">5. Tecnologias utilizadas e justificativa</h2>
<table>
<tr><th>Tecnologia</th><th>Uso</th><th>Por que foi escolhida</th></tr>
<tr><td>Python 3.12+</td><td>Robô completo</td><td>Aceito pelo enunciado; versionável no GitHub; testável; mesma linguagem da API do MVP</td></tr>
<tr><td>requests + xml.etree</td><td>Coleta HTTP e leitura de RSS/Atom</td><td>Bibliotecas padrão de mercado, sem dependências pesadas</td></tr>
<tr><td>JSON Lines</td><td>Logs de auditoria</td><td>Uma linha por evento, legível por pessoas e por ferramentas de análise</td></tr>
<tr><td>FastAPI + SQLite</td><td>API e tela de revisão do MVP que consomem os rascunhos</td><td>Contrato HTTP claro, validação automática do payload, simples de publicar em container</td></tr>
<tr><td>pytest</td><td>Testes automatizados</td><td>Prova os cenários de sucesso, decisão e falha a cada alteração</td></tr>
<tr><td>GitHub Actions</td><td>Agendamento diário e execução sob demanda</td><td>Sem servidor próprio; segredos em GitHub Secrets; logs guardados como artefato</td></tr>
<tr><td>BPMN 2.0</td><td>Documentação do fluxo</td><td>Notação padrão exigida no enunciado</td></tr>
</table>

<h2>6. Regras de negócio, decisões e processamento</h2>
<table>
<tr><th style="width:20%">Decisão</th><th>Regra</th><th style="width:27%">Se não passar</th></tr>
<tr><td>1. Item válido?</td><td>Título com 10+ caracteres; link http(s); domínio do link na lista da fonte; data legível, não futura (tolerância de 1 dia) e com até 180 dias</td><td>Quarentena com o motivo (<code>estado/itens_invalidos.jsonl</code>)</td></tr>
<tr><td>2. Fala de golpe?</td><td>Em fontes gerais, título ou resumo precisa citar palavras como golpe, fraude, estelionato, phishing, clonagem</td><td>Descartado como <code>fora_do_tema</code></td></tr>
<tr><td>3. Já processado?</td><td>Hash SHA-256 de título normalizado (sem acento, minúsculo) + link sem barra final, comparado com a memória de execuções anteriores</td><td>Ignorado como duplicado</td></tr>
<tr><td>4. Tema reconhecido?</td><td>Contagem de palavras-chave em 6 temas: banco falso, Pix de falso parente, código de verificação, falso suporte, falsa promoção, INSS e benefícios</td><td>Rascunho marcado "revisar tema"; o revisor escolhe o tema</td></tr>
<tr><td>5. Entrega aceita?</td><td>API respondeu 201 (criado) ou 409 (já existia)</td><td>Fila de reenvio automático</td></tr>
</table>
<p><b>Processamento do rascunho:</b> HTML removido, resumo cortado em 280 caracteres sem quebrar palavra, três dicas de proteção específicas do tema, crédito à fonte, data de publicação e <code>status = pendente_revisao</code>. O robô nunca publica sozinho.</p>

<h2>7. Tratamento de exceções e recuperação</h2>
<table>
<tr><th>Situação</th><th>Tratamento</th><th style="width:22%">Evidência</th></tr>
<tr><td>Fonte fora do ar, timeout, HTTP 5xx</td><td>3 tentativas com espera crescente; depois registra <code>fonte_indisponivel</code> (ERROR) e segue para a próxima fonte</td><td>Teste + Figura 6</td></tr>
<tr><td>Feed corrompido ou que não é RSS/Atom</td><td><code>fonte_invalida</code> (ERROR) e segue</td><td>Teste</td></tr>
<tr><td>Arquivo JSON/CSV corrompido ou sem colunas</td><td>Movido para <code>entrada/quarentena/</code>; os outros arquivos seguem</td><td>Teste + log</td></tr>
<tr><td>Pasta de entrada ausente</td><td><code>fonte_indisponivel</code></td><td>Teste</td></tr>
<tr><td>Dados duplicados ou inconsistentes</td><td>Duplicado ignorado; inconsistente vai para quarentena com motivo</td><td>Testes + Figura 5</td></tr>
<tr><td>API do MVP desligada ou token recusado</td><td>Rascunho vai para a fila e é reenviado na próxima execução</td><td>Teste + Figuras 6 e 7</td></tr>
<tr><td>Erro inesperado em um item</td><td>Registrado com o tipo do erro; os demais itens continuam</td><td>Código</td></tr>
<tr><td>Configuração ausente ou sem token</td><td>Para com código de saída 2 e mensagem clara</td><td>Teste</td></tr>
</table>
<p><b>Sem falhas silenciosas:</b> toda exceção gera evento no log, e o código de saída é 1 quando algo precisa de atenção (fonte fora, item na fila, erro), o que marca a execução agendada para acompanhamento.</p>

<h2>8. Logs e evidências de auditoria</h2>
<p>Cada execução gera <code>logs/execucao_&lt;id&gt;.jsonl</code> (data e hora UTC, nível, execução, etapa, fonte, item, resultado, mensagem) e <code>logs/resumo_&lt;id&gt;.json</code> com as contagens. Antes de gravar, um filtro mascara CPF, cartão, e-mail, telefone e tokens. Trecho real:</p>
{amostra_log("1_sucesso_execucao_*.jsonl")}
<table>
<tr><th>Resumo da execução (cenário de sucesso)</th><th>Valor</th></tr>
<tr><td>Itens coletados</td><td>{r1['itens_coletados']}</td></tr>
<tr><td>Rascunhos entregues ao MVP</td><td>{r1['rascunhos_entregues']}</td></tr>
<tr><td>Itens inválidos (quarentena)</td><td>{r1['itens_invalidos']} ({e(', '.join(f"{k}: {v}" for k, v in r1['motivos_invalidos'].items()))})</td></tr>
<tr><td>Duplicados ignorados</td><td>{r1['duplicados']}</td></tr>
<tr><td>Rascunhos para revisar o tema</td><td>{r1['sem_tema']}</td></tr>
</table>
{img("assets/01_robo_execucao_api.png", "Figura 2 — Execução do robô em modo API contra o MVP: cada decisão aparece no log.", "media")}

<h2 class="quebra">9. Integração com o MVP</h2>
<p>O resultado do robô é consumido pela API do MVP: <code>POST /api/alertas/rascunhos</code> com <code>Authorization: Bearer</code>. A API valida o formato, responde 201 (criado), 409 (já existe), 401 (token inválido) ou 422 (formato inválido), e guarda o rascunho como pendente. Na tela de revisão, protegida por login, uma pessoa aprova ou rejeita com motivo; só o que é aprovado aparece em <code>/alertas</code>.</p>
<div class="destaque">Execução de ponta a ponta registrada em <code>evidencias/4_integracao/</code>: o robô entregou {integ['execucao_1']['rascunhos_entregues']} rascunhos; pela tela, 4 foram aprovados (um deles com o tema escolhido pelo revisor) e 1 foi rejeitado com motivo. Situação final no MVP: {e(json.dumps(integ['situacao_no_app'], ensure_ascii=False))}. Uma nova execução com o mesmo boletim não gerou nenhum rascunho repetido.</div>
{img(recorte("assets/02_tela_revisao_pendentes.png", 1500), "Figura 3 — Tela de revisão do MVP com os rascunhos recebidos do robô.", "media")}
{img(recorte_trecho("assets/03_revisao_tema_escolhido.png", "cartório"), "Figura 4 — Rascunho sem tema: o revisor escolhe o tema antes de publicar.", "pequena")}
{img(recorte("assets/05_alertas_publicados_computador.png", 1250), "Figura 5 — Página pública de alertas: só aparece o que foi aprovado.", "media")}
{img("assets/06_alertas_publicados_celular.png", "Figura 5b — A mesma página no celular, com letra grande.", "pequena")}

<h2 class="quebra">10. Testes realizados (sucesso, decisão e falha)</h2>
<p>São 22 testes automatizados no robô e 11 no MVP, além do script de ponta a ponta. Todos passam.</p>
<table>
<tr><th style="width:14%">Tipo</th><th>Cenário testado</th><th style="width:30%">Resultado esperado e obtido</th></tr>
<tr><td>Sucesso</td><td>Boletins válidos da pasta de entrada</td><td>5 rascunhos pendentes de revisão</td></tr>
<tr><td>Sucesso</td><td>Feed RSS servido por HTTP</td><td>2 rascunhos com temas corretos</td></tr>
<tr><td>Sucesso</td><td>Entrega à API com token</td><td>5 POSTs com Bearer; fila vazia</td></tr>
<tr><td>Decisão</td><td>Mesmo item no lote e em nova execução</td><td>Nenhum rascunho repetido</td></tr>
<tr><td>Decisão</td><td>Sem link, data futura, origem não permitida, título curto, link inválido, data ilegível, notícia antiga</td><td>Cada um barrado com o motivo certo</td></tr>
<tr><td>Decisão</td><td>Notícia geral sem relação com golpe</td><td>Descartada como fora do tema</td></tr>
<tr><td>Decisão</td><td>Item sem palavra-chave de tema</td><td>Rascunho marcado "revisar tema"</td></tr>
<tr><td>Falha</td><td>Fonte fora do ar</td><td>3 tentativas, erro registrado, outras fontes seguem</td></tr>
<tr><td>Falha</td><td>Feed corrompido e HTTP 500</td><td>Fonte inválida / indisponível, sem travar</td></tr>
<tr><td>Falha</td><td>Arquivo corrompido</td><td>Arquivo em quarentena</td></tr>
<tr><td>Falha</td><td>API desligada e depois religada</td><td>5 na fila; 5 reenviados na execução seguinte</td></tr>
<tr><td>Falha</td><td>Token recusado (401) e item já existente (409)</td><td>Fila / contado como já existente</td></tr>
<tr><td>Falha</td><td>Configuração ausente ou sem token</td><td>Para com mensagem clara</td></tr>
<tr><td>LGPD</td><td>CPF, telefone, e-mail e token em mensagens e na quarentena</td><td>Mascarados</td></tr>
</table>
{img("assets/08_cenario_falha_fonte_e_api.png", "Figura 6 — Falha: feed fora do ar (3 tentativas) e API desligada; os rascunhos vão para a fila.", "media")}
{img("assets/09_cenario_reenvio_da_fila.png", "Figura 7 — Recuperação: na execução seguinte, com a API de volta, a fila é reenviada.", "pequena")}
{img("assets/11_testes_rpa.png", "Figura 8 — Testes automatizados do robô.", "media")}

<h2>11. Segurança e LGPD</h2>
<ul>
<li><b>Minimização:</b> o robô só lê conteúdo público de fontes institucionais; não coleta dados de pessoas.</li>
<li><b>Logs sem dados pessoais:</b> filtro testado que mascara CPF, cartão, e-mail, telefone e tokens.</li>
<li><b>Credenciais fora do código:</b> token do robô e senha do revisor só em variáveis de ambiente e GitHub Secrets; comparação em tempo constante.</li>
<li><b>Menor privilégio:</b> o token do robô só cria rascunhos; publicar exige login de revisor.</li>
<li><b>Sem publicação automática:</b> nada chega ao cidadão sem revisão humana, como pede o princípio de IA e automação responsáveis.</li>
<li><b>Links:</b> o robô não visita os links das notícias; só lê o feed da fonte permitida.</li>
<li><b>Direitos autorais:</b> a Agência Brasil permite a reprodução com crédito; o alerta cita a fonte e usa um resumo curto.</li>
<li><b>Dados de demonstração:</b> os boletins da pasta de exemplo são fictícios e estão identificados como tal.</li>
<li><b>Retenção:</b> logs e estado ficam como artefatos do GitHub Actions pelo prazo padrão; quarentena e fila podem ser apagadas a qualquer momento sem perda de dado pessoal.</li>
</ul>

<h2>12. Links</h2>
<table>
<tr><th style="width:30%">Item</th><th>Link</th></tr>
<tr><td>Repositório GitHub (público)</td><td>{campo(DADOS['link_repositorio'], 'link do repositório')}</td></tr>
<tr><td>Vídeo demonstrativo (até 3 min)</td><td>{campo(DADOS['link_video'], 'link do vídeo')}</td></tr>
<tr><td>MVP publicado</td><td>{campo(DADOS['link_mvp'], 'URL pública do MVP')}</td></tr>
</table>
</body></html>"""


def numerar(w) -> None:
    """Carimba 'página X de N' em todas as páginas, já com a página do BPMN incluída."""
    import io
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas
    total = len(w.pages)
    for i, pag in enumerate(w.pages, 1):
        larg, alt = float(pag.mediabox.width), float(pag.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(larg, alt))
        c.setFont("Helvetica", 7)
        c.setFillGray(0.45)
        c.drawCentredString(larg / 2, 18, f"Relatório Técnico RPA · página {i} de {total}")
        c.save()
        buf.seek(0)
        pag.merge_page(PdfReader(buf).pages[0])


def main():
    html_txt = montar_html()
    pagina = AQUI / "_relatorio.html"
    pagina.write_text(html_txt, encoding="utf-8")
    saida = AQUI / "Relatorio_RPA.pdf"
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME, args=["--allow-file-access-from-files"])
        pg = nav.new_page()
        pg.goto(pagina.as_uri())
        pg.wait_for_load_state("networkidle")
        pg.pdf(path=str(saida), format="A4", print_background=True, prefer_css_page_size=True)
        bpmn_html = AQUI / "_bpmn.html"
        bpmn_html.write_text(f"""<!doctype html><html><head><meta charset='utf-8'><style>
@page {{ size: A4 landscape; margin: 10mm; }}
body {{ font-family: Arial, sans-serif; color:#1b2433; margin:0 }}
h2 {{ font-size: 13.5pt; color:#0b3d6e; border-bottom:1.5pt solid #0b3d6e; margin:0 0 6pt; padding-bottom:2pt }}
img {{ width:100%; border:0.6pt solid #c5ccd6 }} p {{ font-size:8.6pt; color:#4a5568; text-align:center }}
</style></head><body><h2>4. Desenho do fluxo (BPMN 2.0)</h2>
<img src='{(RPA / 'docs' / 'fluxo-rpa-alertas.png').as_uri()}'>
<p>Figura 1 — Fluxo BPMN: duas repetições (subprocessos multi-instância), cinco decisões, exceções com eventos de fim e
mensagem para a revisão humana no MVP. Arquivo editável: docs/fluxo-rpa-alertas.bpmn</p></body></html>""", encoding="utf-8")
        pg.goto(bpmn_html.as_uri())
        pg.wait_for_load_state("networkidle")
        bpmn_pdf = AQUI / "_bpmn.pdf"
        pg.pdf(path=str(bpmn_pdf), landscape=True, format="A4", print_background=True, prefer_css_page_size=True)
        nav.close()
    from pypdf import PdfReader, PdfWriter
    principal = PdfReader(str(saida))
    alvo = next(i for i, pag in enumerate(principal.pages) if "5. Tecnologias" in (pag.extract_text() or ""))
    w = PdfWriter()
    for i, pag in enumerate(principal.pages):
        if i == alvo:
            w.add_page(PdfReader(str(bpmn_pdf)).pages[0])
        w.add_page(pag)
    numerar(w)
    with open(saida, "wb") as f:
        w.write(f)
    for tmp in (pagina, bpmn_html, bpmn_pdf):
        tmp.unlink()
    import shutil
    shutil.rmtree(AQUI / "_tmp", ignore_errors=True)
    print("gerado:", saida)


if __name__ == "__main__":
    main()
