# StageFlow

Aplicação local para identificar, revisar, calcular e preencher documentos de
estágio em DOCX. O sistema não escreve conteúdo acadêmico: introdução,
desenvolvimento das atividades, conclusão e referências permanecem em branco
para edição manual.

## Fluxo

1. Cole na interface a mensagem recebida do aluno.
2. Regras locais identificam primeiro os campos padronizados.
3. O Ollama usa o contexto completo para organizar os campos ainda vazios, mesmo
   quando as respostas estão em linhas soltas, fora de ordem ou sem rótulos.
4. Revise separadamente os dados que deveriam vir do aluno.
5. Consulte ou reutilize a empresa cadastrada pelo CNPJ.
6. Selecione curso, situação regular ou DP, módulo e área.
7. Informe a data inicial; o sistema calcula todos os dias até fechar a carga.
8. Cole as atividades ou clique em "Sugerir atividades com IA local", revise a prévia
   e use as sugestões que fizerem sentido. Distribua as horas por peso ou manualmente.
9. Confirme a revisão e gere relatório, plano e termo de compromisso.

A geração fica bloqueada enquanto houver campos obrigatórios ausentes, carga
inválida ou atividades sem fechar o total do módulo. Sugestões de dados do aluno
feitas pela IA sempre mostram o trecho de origem e nunca são usadas para
inventar dados ausentes.

## Regras acadêmicas e calendário

O módulo regular é calculado pelo curso e semestre. Farmácia possui os módulos I
a VI entre o 3º e o 8º semestre, com cargas de 130h, 130h, 130h, 140h, 150h e
160h. Biomedicina possui módulo I no 7º semestre (320h) e módulo II no 8º (360h).
Em dependência, o módulo é escolhido manualmente e independe do semestre atual.

O calendário usa por padrão segunda a sexta-feira, das 08h00 às 14h00. Ele:

- limita o estágio a 6 horas diárias e 30 horas semanais;
- sugere feriados nacionais e estaduais conforme a UF da empresa;
- aceita feriados municipais e outras exclusões informadas manualmente;
- calcula a data final, os dias efetivamente trabalhados e a carga semanal;
- reduz apenas o último dia para fechar exatamente a carga do módulo.

Horário e dias da semana podem ser alterados em `Ajustar horário ou calendário`.

## Empresas e histórico de atividades

Os dados públicos da empresa são salvos localmente em `data/stageflow.db`, usando
o CNPJ como identificador. Em uma nova demanda com o mesmo CNPJ, use `Buscar no
cadastro local`. O botão `Abrir consulta oficial` facilita a conferência de uma
empresa ainda não cadastrada.

O mesmo banco registra os títulos das atividades depois que os documentos são
gerados. Atividades iguais ou muito semelhantes na mesma área produzem um aviso.
Na etapa de atividades, informe a quantidade e escolha um modelo do Ollama.
"Sugerir atividades com IA local" executa uma chamada independente, somente ao
clicar: envia curso, módulo, área, quantidade e até 30 títulos recentes, sem os
dados pessoais ou a mensagem do aluno. A resposta é apenas uma lista de títulos.
Atividades-base podem se repetir entre alunos; a combinação e os títulos devem
ser variados. A prévia não substitui o que já foi preenchido. Só "Usar estas
sugestões" aplica os títulos ao campo editável e reinicia a distribuição de horas
e a confirmação final. Falhas da IA preservam o preenchimento manual.
O prompt copiável para o ChatGPT continua disponível. O StageFlow distribui as
horas, mas não escreve o texto acadêmico. As sugestões não comprovam atividades
realizadas: confira a compatibilidade e confirme a experiência real do aluno.

## Execução rápida

Pré-requisitos:

- Windows com WSL/Ubuntu;
- Ollama aberto no Windows;
- ao menos um modelo instalado no Ollama;
- ambiente `.venv` do projeto com as dependências instaladas.

Na primeira execução ou após atualizar as dependências, estando no WSL:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Se o seu terminal mostra `bash` ou `zsh`, abra a interface com:

```bash
./executar.sh
```

Se estiver usando o PowerShell do Windows, use:

```powershell
.\executar.ps1
```

O navegador abrirá em `http://localhost:8501`. Mantenha o terminal aberto
enquanto estiver usando o sistema e pressione `Ctrl+C` para encerrá-lo. Para
usar outra porta no WSL, execute `STAGEFLOW_PORT=8502 ./executar.sh`.

## Ollama

O modelo padrão é `qwen3:8b`. A interface lista automaticamente os modelos
instalados e permite escolher outro. A configuração também pode ser alterada por
variáveis de ambiente:

```text
STAGEFLOW_OLLAMA_MODEL=qwen3:8b
OLLAMA_HOST=http://localhost:11434
```

O StageFlow usa a API local do Ollama. A mensagem bruta não é enviada para
serviços externos nem gravada pelo aplicativo. Depois da geração, os documentos
são salvos em `output/docx` e o cadastro confirmado da empresa e o histórico de
atividades ficam no banco local `data/stageflow.db`.

## Linha de comando

A interface é o fluxo principal. Para processar uma mensagem padronizada sem
abrir o navegador no PowerShell:

```powershell
.\gerar.ps1
```

No WSL, o equivalente é:

```bash
./gerar.sh
```

Opções úteis:

```powershell
.\gerar.ps1 -SemIA
.\gerar.ps1 -Modelo llama3.1:8b
.\gerar.ps1 -Saida output/demandas/aluno_exemplo
.\gerar.ps1 -Sobrescrever
```

No WSL, as opções seguem o formato da linha de comando, por exemplo:

```bash
./gerar.sh --sem-ia
./gerar.sh --model llama3.1:8b
./gerar.sh --output output/demandas/aluno_exemplo --overwrite
```

## Campos e validações

Os dados são agrupados em aluno, dados acadêmicos, empresa, responsável técnico,
estágio e seguro. O sistema verifica:

- presença dos 39 campos obrigatórios finais;
- formato de CPF, CNPJ, e-mails e datas;
- ordem cronológica das datas;
- cobertura do seguro durante o estágio;
- compatibilidade entre área, conselho e cargo profissional;
- duplicidades e trechos não reconhecidos da mensagem;
- placeholders no corpo, tabelas, cabeçalhos, rodapés e caixas de texto.

## Estrutura

```text
stageflow_ia/
|-- .streamlit/config.toml
|-- data/mensagem_zap.example.txt
|-- src/stageflow/
|   |-- academics.py       # módulos e cargas por curso/semestre
|   |-- activities.py      # distribuição e prompt de atividades
|   |-- scheduling.py      # calendário e feriados
|   |-- repository.py      # empresas e histórico no SQLite local
|   |-- fields.py          # catálogo único dos campos
|   |-- models.py          # objetos de domínio
|   |-- extraction.py      # regras, Ollama e estratégia híbrida
|   |-- validation.py      # erros e avisos determinísticos
|   |-- enrichment.py      # datas e campos derivados
|   |-- template_engine.py # substituição de placeholders
|   |-- documents.py       # geração transacional dos três DOCX
|   |-- workflow.py        # caso de uso independente da interface
|   |-- ui.py              # interface Streamlit
|   `-- cli.py             # linha de comando
|-- templates/
|-- tests/
|-- executar.ps1
|-- executar.sh
|-- gerar.ps1
|-- gerar.sh
`-- requirements.txt
```

## Testes

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Projetos/stageflow_ia && PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v'
```

Também é possível validar a compilação:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Projetos/stageflow_ia && .venv/bin/python -m compileall -q src tests'
```
