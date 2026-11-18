"""Gera docs/fluxo-rpa-alertas.bpmn (BPMN 2.0 com diagrama), abrível no bpmn.io e no Camunda Modeler.

Uso: python docs/gerar_bpmn.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

SAIDA = Path(__file__).resolve().parent / "fluxo-rpa-alertas.bpmn"
ASPAS = {'"': "&quot;"}

shapes = {}   # id -> (x, y, w, h)
nodes = {}    # processo -> lista de xml
edges = []    # (id, origem, destino, nome, waypoints, processo)

EV, TK, GW = (36, 36), (120, 80), (50, 50)


def add(proc, id_, tag, nome, x, y, size, extra="", attrs=""):
    w, h = size
    shapes[id_] = (x, y, w, h)
    corpo = f">{extra}</bpmn:{tag}>" if extra else "/>"
    if tag in ("subProcess",):
        corpo = ">" + extra  # fechado depois
    nodes.setdefault(proc, []).append(
        f'<bpmn:{tag} id="{id_}" name="{escape(nome, ASPAS)}"{attrs}{corpo}')


def fecha(proc, tag):
    nodes[proc].append(f"</bpmn:{tag}>")


def cx(i): x, y, w, h = shapes[i]; return x + w / 2
def cy(i): x, y, w, h = shapes[i]; return y + h / 2
def direita(i): x, y, w, h = shapes[i]; return (x + w, y + h / 2)
def esquerda(i): x, y, w, h = shapes[i]; return (x, y + h / 2)
def topo(i): x, y, w, h = shapes[i]; return (x + w / 2, y)
def base(i): x, y, w, h = shapes[i]; return (x + w / 2, y + h)


def flow(proc, id_, a, b, nome="", pts=None):
    pts = pts or [direita(a), esquerda(b)]
    edges.append((id_, a, b, nome, pts, proc))
    n = f' name="{nome}"' if nome else ""
    nodes[proc].append(f'<bpmn:sequenceFlow id="{id_}" sourceRef="{a}" targetRef="{b}"{n}/>')


MI = '<bpmn:multiInstanceLoopCharacteristics isSequential="true"/>'
P = "Processo_Robo"
R = "Processo_Revisao"

# ---------------- Pool 1: robô ----------------
add(P, "Inicio", "startEvent", "Agendamento diário (06h17)", 80, 242, EV,
    '<bpmn:timerEventDefinition id="TimerDiario"><bpmn:timeCycle>0 17 6 * * ?</bpmn:timeCycle></bpmn:timerEventDefinition>')
add(P, "T_Config", "task", "Carregar configuração e fontes permitidas", 160, 220, TK)
add(P, "T_Fila", "task", "Reenviar rascunhos da fila pendente", 320, 220, TK)

add(P, "SP_Fontes", "subProcess", "Para cada fonte ativa", 480, 40, (1740, 490), MI)
add(P, "IniFonte", "startEvent", "", 500, 242, EV)
add(P, "T_Coletar", "task", "Coletar fonte (timeout, até 3 tentativas)", 570, 220, TK)
add(P, "G_Respondeu", "exclusiveGateway", "Fonte respondeu?", 730, 235, GW)
add(P, "T_FonteFalha", "task", "Registrar fonte indisponível ou inválida", 705, 330, (100, 70))
add(P, "FimFonteFalha", "endEvent", "Segue para a próxima fonte", 737, 424, EV)

add(P, "SP_Itens", "subProcess", "Para cada item coletado", 830, 60, (1240, 440), MI)
add(P, "IniItem", "startEvent", "", 850, 242, EV)
add(P, "T_Validar", "task", "Validar título, link, data e origem", 910, 220, TK)
add(P, "G_Valido", "exclusiveGateway", "Item válido?", 1070, 235, GW)
add(P, "T_Quarentena", "task", "Mover para quarentena com motivo", 1045, 330, (100, 70))
add(P, "FimQuarentena", "endEvent", "Item barrado", 1077, 424, EV)
add(P, "G_Duplicado", "exclusiveGateway", "Já processado (hash)?", 1200, 235, GW)
add(P, "T_Duplicado", "task", "Registrar duplicado e ignorar", 1175, 330, (100, 70))
add(P, "FimDuplicado", "endEvent", "Item ignorado", 1207, 424, EV)
add(P, "T_Classificar", "task", "Classificar tema por palavras-chave", 1300, 220, TK)
add(P, "G_Tema", "exclusiveGateway", "Tema reconhecido?", 1460, 235, GW)
add(P, "T_RevisarTema", "task", "Marcar \"revisar tema\"", 1435, 90, (100, 70))
add(P, "T_Rascunho", "task", "Montar rascunho educativo em linguagem simples", 1560, 220, TK)
add(P, "T_Enviar", "sendTask", "Enviar rascunho à API do MVP (token)", 1710, 220, TK)
add(P, "G_Aceito", "exclusiveGateway", "Entrega aceita?", 1860, 235, GW)
add(P, "T_FilaReenvio", "task", "Guardar na fila de reenvio", 1835, 330, (100, 70))
add(P, "FimFila", "endEvent", "Reenvio na próxima execução", 1867, 424, EV)
add(P, "FimItem", "endEvent", "Rascunho pendente de revisão", 1990, 242, EV)

flow(P, "f_i1", "IniItem", "T_Validar")
flow(P, "f_i2", "T_Validar", "G_Valido")
flow(P, "f_i3", "G_Valido", "T_Quarentena", "não", [base("G_Valido"), topo("T_Quarentena")])
flow(P, "f_i4", "T_Quarentena", "FimQuarentena", "", [base("T_Quarentena"), topo("FimQuarentena")])
flow(P, "f_i5", "G_Valido", "G_Duplicado", "sim")
flow(P, "f_i6", "G_Duplicado", "T_Duplicado", "sim", [base("G_Duplicado"), topo("T_Duplicado")])
flow(P, "f_i7", "T_Duplicado", "FimDuplicado", "", [base("T_Duplicado"), topo("FimDuplicado")])
flow(P, "f_i8", "G_Duplicado", "T_Classificar", "não")
flow(P, "f_i9", "T_Classificar", "G_Tema")
flow(P, "f_i10", "G_Tema", "T_RevisarTema", "não", [topo("G_Tema"), base("T_RevisarTema")])
flow(P, "f_i11", "T_RevisarTema", "T_Rascunho", "",
     [direita("T_RevisarTema"), (cx("T_Rascunho"), cy("T_RevisarTema")), topo("T_Rascunho")])
flow(P, "f_i12", "G_Tema", "T_Rascunho", "sim")
flow(P, "f_i13", "T_Rascunho", "T_Enviar")
flow(P, "f_i14", "T_Enviar", "G_Aceito")
flow(P, "f_i15", "G_Aceito", "T_FilaReenvio", "não", [base("G_Aceito"), topo("T_FilaReenvio")])
flow(P, "f_i16", "T_FilaReenvio", "FimFila", "", [base("T_FilaReenvio"), topo("FimFila")])
flow(P, "f_i17", "G_Aceito", "FimItem", "sim")
fecha(P, "subProcess")  # fecha SP_Itens

add(P, "FimFonte", "endEvent", "Fonte concluída", 2130, 242, EV)
flow(P, "f_f1", "IniFonte", "T_Coletar")
flow(P, "f_f2", "T_Coletar", "G_Respondeu")
flow(P, "f_f3", "G_Respondeu", "T_FonteFalha", "não", [base("G_Respondeu"), topo("T_FonteFalha")])
flow(P, "f_f4", "T_FonteFalha", "FimFonteFalha", "", [base("T_FonteFalha"), topo("FimFonteFalha")])
flow(P, "f_f5", "G_Respondeu", "SP_Itens", "sim", [direita("G_Respondeu"), (shapes["SP_Itens"][0], 260)])
flow(P, "f_f6", "SP_Itens", "FimFonte", "", [(shapes["SP_Itens"][0] + shapes["SP_Itens"][2], 260), esquerda("FimFonte")])
fecha(P, "subProcess")  # fecha SP_Fontes

add(P, "T_Resumo", "task", "Gravar resumo, logs JSONL e estado", 2260, 220, TK)
add(P, "Fim", "endEvent", "Execução concluída", 2420, 242, EV)
flow(P, "f_1", "Inicio", "T_Config")
flow(P, "f_2", "T_Config", "T_Fila")
flow(P, "f_3", "T_Fila", "SP_Fontes", "", [direita("T_Fila"), (shapes["SP_Fontes"][0], 260)])
flow(P, "f_4", "SP_Fontes", "T_Resumo", "", [(shapes["SP_Fontes"][0] + shapes["SP_Fontes"][2], 260), esquerda("T_Resumo")])
flow(P, "f_5", "T_Resumo", "Fim")

# ---------------- Pool 2: revisão humana no MVP ----------------
add(R, "R_Inicio", "startEvent", "Rascunho recebido", 1752, 692, EV,
    '<bpmn:messageEventDefinition id="MsgRascunho"/>')
add(R, "R_Revisar", "userTask", "Revisor confere o rascunho na tela de revisão", 1850, 670, TK)
add(R, "R_Aprova", "exclusiveGateway", "Aprovado?", 2010, 685, GW)
add(R, "R_Publicar", "task", "Publicar em \"Alertas\" no app", 2100, 625, TK)
add(R, "R_FimPub", "endEvent", "Alerta visível para o cidadão", 2270, 647, EV)
add(R, "R_Rejeitar", "task", "Rejeitar com motivo", 2100, 730, TK)
add(R, "R_FimRej", "endEvent", "Não publicado", 2270, 752, EV)
flow(R, "r1", "R_Inicio", "R_Revisar")
flow(R, "r2", "R_Revisar", "R_Aprova")
flow(R, "r3", "R_Aprova", "R_Publicar", "sim", [topo("R_Aprova"), (cx("R_Aprova"), cy("R_Publicar")), esquerda("R_Publicar")])
flow(R, "r4", "R_Aprova", "R_Rejeitar", "não", [base("R_Aprova"), (cx("R_Aprova"), cy("R_Rejeitar")), esquerda("R_Rejeitar")])
flow(R, "r5", "R_Publicar", "R_FimPub")
flow(R, "r6", "R_Rejeitar", "R_FimRej")

POOLS = {"Pool_Robo": ("Robô RPA de alertas (Python)", P, 0, 0, 2520, 570),
         "Pool_Revisao": ("MVP: revisão humana e publicação", R, 0, 610, 2520, 240)}


def ws(pts):
    return "".join(f'<di:waypoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in pts)


def montar() -> str:
    partes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
              'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
              'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
              'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
              'id="Definicoes_RPA" targetNamespace="http://gs-fiap-2026/rpa-alertas" '
              'exporter="gerar_bpmn.py" exporterVersion="1.0">',
              '<bpmn:collaboration id="Colaboracao">']
    for pid, (nome, proc, *_r) in POOLS.items():
        partes.append(f'<bpmn:participant id="{pid}" name="{escape(nome)}" processRef="{proc}"/>')
    partes.append('<bpmn:messageFlow id="MF_Rascunho" name="POST /api/alertas/rascunhos" '
                  'sourceRef="T_Enviar" targetRef="R_Inicio"/>')
    partes.append("</bpmn:collaboration>")
    for proc in (P, R):
        partes.append(f'<bpmn:process id="{proc}" isExecutable="false">')
        partes.extend(nodes[proc])
        partes.append("</bpmn:process>")
    partes.append('<bpmndi:BPMNDiagram id="Diagrama"><bpmndi:BPMNPlane id="Plano" bpmnElement="Colaboracao">')
    for pid, (_n, _p, x, y, w, h) in POOLS.items():
        partes.append(f'<bpmndi:BPMNShape id="{pid}_di" bpmnElement="{pid}" isHorizontal="true">'
                      f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}"/></bpmndi:BPMNShape>')
    for i, (x, y, w, h) in shapes.items():
        exp = ' isExpanded="true"' if i.startswith("SP_") else ""
        partes.append(f'<bpmndi:BPMNShape id="{i}_di" bpmnElement="{i}"{exp}>'
                      f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}"/></bpmndi:BPMNShape>')
    for id_, _a, _b, _n, pts, _p in edges:
        partes.append(f'<bpmndi:BPMNEdge id="{id_}_di" bpmnElement="{id_}">{ws(pts)}</bpmndi:BPMNEdge>')
    partes.append(f'<bpmndi:BPMNEdge id="MF_Rascunho_di" bpmnElement="MF_Rascunho">'
                  f'{ws([base("T_Enviar"), (cx("T_Enviar"), 590), (cx("R_Inicio"), 590), topo("R_Inicio")])}'
                  f'</bpmndi:BPMNEdge>')
    partes.append("</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>")
    return "\n".join(partes)


if __name__ == "__main__":
    SAIDA.write_text(montar(), encoding="utf-8")
    print(f"gerado: {SAIDA}")
