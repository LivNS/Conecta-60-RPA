# Robô de alertas de golpes (RPA)

Componente **Automação** da CitizenTech da equipe (GS FIAP 2026.2, Engenharia de Software 4º ano).

| Integrante (nome completo) | RM |
| --- | --- |
| _preencher_ | _preencher_ |
| _preencher_ | _preencher_ |
| _preencher_ | _preencher_ |

**Links:** repositório _preencher_ · vídeo (até 3 min) _preencher_ · MVP publicado _preencher_
**Relatório técnico:** [`docs/relatorio/Relatorio_RPA.pdf`](docs/relatorio/Relatorio_RPA.pdf) · **Fluxo BPMN:** [`docs/fluxo-rpa-alertas.bpmn`](docs/fluxo-rpa-alertas.bpmn) ([imagem](docs/fluxo-rpa-alertas.png)) · **Roteiro do vídeo:** [`docs/roteiro_video.md`](docs/roteiro_video.md)

## O problema que o robô resolve

Golpes novos surgem toda semana. Sem automação, alguém precisaria vasculhar avisos de órgãos e entidades, copiar, conferir se já foi publicado e reescrever em linguagem simples. O robô faz esse trabalho repetitivo e **entrega rascunhos educativos para revisão humana**. Nada é publicado para a pessoa idosa sem aprovação.

## Como rodar

```bash
cd rpa
pip install -r requirements.txt
cp exemplos/entrada/* entrada/            # boletins fictícios de demonstração
PYTHONPATH=src python -m rpa_alertas --config config/fontes.json
python -m pytest -q                       # 22 testes: sucesso, decisão e falha
python scripts/demonstrar_cenarios.py     # gera evidencias/ dos 3 cenários
cd .. && python scripts/integracao_ponta_a_ponta.py   # robô + app de verdade, com prints em assets/
```

Código de saída: `0` tudo certo; `1` algo precisa de atenção (fonte fora do ar, item na fila, erro inesperado); `2` configuração inválida.

## Fluxo

1. **Entrada:** lista de fontes permitidas em `config/fontes.json`: o feed RSS público da Agência Brasil (fonte real; a agência permite reprodução com crédito) e uma pasta de boletins JSON/CSV.
2. **Reenvio:** rascunhos que ficaram na fila em execuções anteriores são reenviados primeiro.
3. **Repetição sobre fontes:** coleta com timeout e até 3 tentativas. Fonte fora do ar é registrada e o robô segue para a próxima.
4. **Repetição sobre itens:** validar → checar se fala de golpe → deduplicar → classificar tema → montar rascunho → entregar.
5. **Saída:** rascunhos com `status: pendente_revisao`, logs JSONL e resumo da execução.

## Regras de negócio (decisões)

| Decisão | Regra | Se não passar |
| --- | --- | --- |
| Item válido? | Título com 10+ caracteres; link http(s); domínio do link na lista da fonte; data legível, não futura e com até 180 dias | Vai para `estado/itens_invalidos.jsonl` com o motivo |
| Fala de golpe? | Em fontes gerais (`palavras_relevancia`), título ou resumo precisa citar golpe, fraude, estelionato, phishing, clonagem etc. | Descartado como `fora_do_tema` |
| Já existe? | Hash de título normalizado + link (sem barra final) comparado com `estado/vistos.json` | Ignorado e registrado como duplicado |
| Tema reconhecido? | Contagem de palavras-chave em 6 temas (banco falso, Pix de falso parente, código de verificação, falso suporte, falsa promoção, INSS e benefícios) | Rascunho marcado `revisar_tema` para o revisor |
| Entrega aceita? | API respondeu 200/201 (409 = já existia) | Vai para `estado/fila_reenvio.jsonl` e é reenviado na próxima execução |

## Tratamento de exceções

| Situação | Tratamento |
| --- | --- |
| Fonte fora do ar, timeout, HTTP 5xx | 3 tentativas com espera crescente; depois `fonte_indisponivel` (ERROR) e segue |
| Feed corrompido | `fonte_invalida` (ERROR) e segue |
| Arquivo JSON/CSV corrompido ou sem colunas | Movido para `entrada/quarentena/` |
| Pasta de entrada ausente | `fonte_indisponivel` |
| Item duplicado ou inconsistente | Ignorado ou em quarentena, com motivo no log |
| API do MVP desligada ou token recusado | Fila local + reenvio automático |
| Erro inesperado num item | Registrado; os outros itens continuam |
| Configuração ausente ou sem token no modo API | Para com código 2 e mensagem clara |

## Integração com o MVP

Dois modos, definidos em `modo_entrega`:

- **`api`** (alvo): `POST {RPA_API_URL}/api/alertas/rascunhos` com `Authorization: Bearer {RPA_API_TOKEN}`. O MVP mostra o rascunho na tela de revisão; aprovado, aparece em "Alertas".
- **`arquivo`** (alternativa sem rede): grava `saida/rascunhos.json` de forma atômica.

A API está implementada em [`../app`](../app): recebe o rascunho (201/409/401/422), mostra na tela de revisão protegida por login e só publica em `/alertas` o que a pessoa aprova. A execução de ponta a ponta está em `evidencias/4_integracao/` e nos prints `assets/01` a `07`.

Contrato do rascunho: `id, titulo, tema, tema_rotulo, resumo_simples, como_se_proteger[], fonte_nome, link_fonte, data_publicacao, precisa_revisar_tema, status, origem, criado_em`.

## Logs e auditoria

Cada execução gera `logs/execucao_<id>.jsonl` (uma linha por evento: data/hora UTC, nível, etapa, fonte, item, resultado, mensagem) e `logs/resumo_<id>.json` (contagens). Amostras em `logs/amostras/`. Mensagens passam por um filtro que mascara CPF, cartão, e-mail, telefone e tokens.

## Agendamento

`.github/workflows/rpa-alertas.yml` roda os testes e o robô todo dia às 06h17 (Brasília) e também sob demanda. A pasta `estado/` é preservada entre execuções por cache, e os logs ficam como artefato de cada execução. Token e URL da API ficam em GitHub Secrets.

## Segurança e LGPD

- O robô só lê conteúdo público de fontes institucionais; não coleta dados de pessoas.
- Links das notícias nunca são abertos pelo robô; ele só lê o feed da fonte permitida.
- Credenciais só em variáveis de ambiente e GitHub Secrets; nada no repositório.
- Logs sem dados pessoais (filtro testado em `tests/`).

## Dados de demonstração

`exemplos/entrada/` e `exemplos/entrada_extra/` contêm **boletins fictícios** (domínios `exemplo.org` e `exemplo.gov.br`), montados para exercitar cada regra: 4 válidos com temas diferentes, 1 duplicado, 1 sem link, 1 com data no futuro, 1 sem tema, 1 de origem não permitida e 1 arquivo corrompido. A fonte real (Agência Brasil) roda junto; se estiver fora do ar, o robô registra e segue com as demais.

## Estrutura

```
rpa/
  config/fontes.json        lista de fontes permitidas e modo de entrega
  src/rpa_alertas/          código (coleta, regras, rascunho, envio, registro, robo)
  tests/                    22 testes: sucesso, decisão e falha
  scripts/                  demonstração dos 3 cenários
  exemplos/entrada/         boletins fictícios
  evidencias/               saídas dos 3 cenários
  logs/amostras/            amostras de log sem dados sensíveis
  docs/                     BPMN (.bpmn + .png), relatório PDF e gerador, roteiro do vídeo
  assets/                   prints: execução, revisão, publicação, falha, reenvio, testes
```
