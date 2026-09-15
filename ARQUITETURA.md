# Arquitetura — Filtro Sísmico Passa-Baixa (GIECAR/UFF)

## 1. Stack tecnológica e justificativas

| Camada | Escolha | Por quê |
|---|---|---|
| UI | **PyQt5** (widgets nativos) | Exigido pelo enunciado; sem QSS custom |
| Threading | **QThread + QObject worker (moveToThread)** | Mais robusto que QRunnable para long-running job com sinais de progresso; QRunnable é melhor para tarefas curtas/paralelas (usado no bônus de multiprocessing) |
| Leitura SEG-Y | **segyio** (modo streaming, `segyio.open`) | Padrão da indústria, permite leitura lazy de trace headers e traços individuais sem carregar o volume inteiro |
| Filtro | **scipy.signal** (`butter` + `sosfiltfilt` ou `sosfilt`) | `sos` (second-order sections) é numericamente mais estável que `ba` para ordens mais altas |
| Persistência de traços | **HDF5 via h5py** | Escrita incremental nativa (`resizable dataset` com `maxshape`), chunking configurável, amplamente usado em geofísica. Zarr seria equivalente e melhor para paralelismo/cloud, mas HDF5 tem tooling mais maduro para uso local single-file — justificativa a detalhar no README |
| Persistência de metadados | **SQLite + SQLAlchemy** (com Alembic p/ migrations) | Exigido; SQLite é suficiente para app desktop single-user |
| Processamento paralelo (opcional) | **multiprocessing.Pool** | Paraleliza filtragem entre chunks de traços, mantendo streaming (cada worker processa e devolve um chunk, nunca o volume todo) |
| Testes | **pytest + pytest-qt** | Unitários de negócio + 1 E2E simulando fluxo real |

## 2. Estrutura de pastas

```
giecar_seismic_filter/
├── app/
│   ├── __init__.py
│   ├── main.py                      # entry point, monta QApplication
│   │
│   ├── domain/                      # === camada de negócio (sem Qt aqui) ===
│   │   ├── __init__.py
│   │   ├── models.py                 # SeismicDataset, Job (dataclasses)
│   │   ├── job_state_machine.py      # transições de estado + validação
│   │   ├── filter_service.py         # create_filter_job, run_filter_job, cancel_job...
│   │   ├── butterworth.py            # lógica pura do filtro (testável isolada)
│   │   ├── segy_reader.py            # wrapper streaming sobre segyio
│   │   └── exceptions.py
│   │
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── db.py                     # engine, session factory SQLAlchemy
│   │   ├── models_orm.py             # tabelas: datasets, jobs, job_logs
│   │   ├── repository.py             # CRUD desacoplado do domain
│   │   ├── trace_store.py            # escrita/leitura incremental HDF5
│   │   └── migrations/               # Alembic
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── filter_worker.py          # QObject worker, roda em QThread
│   │   └── cancel_token.py           # objeto thread-safe (threading.Event)
│   │
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py            # QMainWindow, monta as telas
│       ├── import_view.py            # tela "Importar Sísmica"
│       ├── filter_config_view.py     # tela "Configurar Filtro"
│       ├── execution_view.py         # tela "Execução/Progresso"
│       ├── history_view.py           # tela "Histórico de Jobs"
│       └── spectrum_widget.py        # (opcional) QC visual antes/depois
│
├── tests/
│   ├── unit/
│   │   ├── test_butterworth.py       # corretude + resposta em frequência
│   │   ├── test_job_state_machine.py
│   │   ├── test_filter_service.py    # validações (Nyquist, ordem, dataset)
│   │   └── test_streaming_memory.py  # garante pico de memória ~constante
│   ├── e2e/
│   │   └── test_full_pipeline.py     # import → filtro → persistência
│   └── conftest.py                   # fixtures: dataset sintético pequeno
│
├── scripts/
│   └── generate_synthetic_segy.py    # gera .sgy pequeno p/ testes locais
│
├── benchmarks/
│   └── memory_streaming_vs_naive.py  # item opcional
│
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

**Regra de ouro da arquitetura:** nada em `domain/` importa `PyQt5`. Isso garante que os contratos (`create_filter_job`, `run_filter_job`, etc.) rodem em pytest puro, sem precisar de `pytest-qt` nem de um `QApplication` de pé.

## 3. Modelo de dados

### `SeismicDataset` (domain + ORM)
```python
id: str (uuid)
name: str
source_path: str
n_inlines: int
n_crosslines: int
n_samples: int
sample_rate_ms: float
created_at: datetime
```
Populado no import lendo **apenas trace headers** via `segyio.open(path, ignore_geometry=...)`.

### `Job`
```python
id: str (uuid)
dataset_id: str (FK)
status: JobStatus            # enum: CREATED, RUNNING, COMPLETED, FAILED, CANCELLED
cutoff_hz: float
order: int
progress_pct: float
output_path: str | None
error_message: str | None
created_at: datetime
started_at: datetime | None
finished_at: datetime | None
```

### `JobStateMachine`
Transições válidas (refletindo o diagrama):
```
CREATED   → RUNNING
RUNNING   → COMPLETED
RUNNING   → FAILED
RUNNING   → CANCELLED
```
Qualquer outra transição levanta `InvalidTransitionError`. Isso é testado isoladamente em `test_job_state_machine.py` — é a parte mais fácil de "ganhar pontos" com poucos testes bem escritos.

## 4. Fluxo de threading (UI responsiva)

```
[MainWindow]
   |
   | cria FilterWorker(job_id) e QThread
   | worker.moveToThread(thread)
   |
   | thread.started -> worker.run()
   | worker.progress(pct)      -> slot atualiza QProgressBar (queued connection)
   | worker.finished(job)      -> slot atualiza UI, thread.quit()
   | worker.error(msg)         -> slot mostra erro
   |
   | botão Cancelar -> cancel_token.set() (thread-safe, threading.Event)
   |                   worker checa token a cada chunk processado
```

Nenhum acesso a widget acontece dentro do worker — só emite sinais. A UI só lê/escreve widgets no thread principal, via slots conectados por `Qt.QueuedConnection` (padrão quando threads diferentes).

## 5. Streaming: como garantir memória O(1) nos traços

Pipeline por chunk (ex: 500 traços por vez, configurável):

```
for chunk_idx, trace_indices in enumerate(chunks(n_traces, chunk_size)):
    raw_chunk = segy_reader.read_traces(trace_indices)      # streaming, só esse chunk em RAM
    filtered_chunk = butterworth.apply(raw_chunk, cutoff_hz, order, sample_rate_ms)
    trace_store.write_chunk(filtered_chunk, trace_indices)   # HDF5 resizable dataset
    pct = (chunk_idx + 1) / n_total_chunks * 100
    progress_callback(pct)
    if cancel_token.is_set():
        trace_store.rollback_partial()  # opcional
        raise JobCancelled()
```

`trace_store.py` usa `h5py.File(..., 'a')` com dataset criado via `create_dataset(..., maxshape=(None, n_samples), chunks=True)` e `.resize()` a cada chunk — nunca aloca o array completo.

O teste `test_streaming_memory.py` usa `tracemalloc` ou `resource.getrusage` para garantir que o pico de memória não escala com o tamanho do arquivo de entrada (roda com datasets sintéticos de tamanhos diferentes e compara).

## 6. Trilha de criatividade — recomendação

Entre as 4 opções, sugiro **"Retomar (resume) um job interrompido a partir do último chunk processado com sucesso"**:
- Reaproveita a mesma infraestrutura de streaming/chunking já exigida no core (baixo custo incremental)
- É o item que mais conecta com a história do cliente no enunciado (processamento que trava a estação de madrugada) — resposta direta à dor relatada
- Tecnicamente: persistir `last_completed_chunk_idx` no `Job`, e ao reiniciar checar se existe output parcial + esse índice, retomando a leitura/escrita a partir dali

Se preferir algo de menor esforço, "Limitar intervalos de inline/xline" é o mais simples de implementar (só filtra o range antes do loop de streaming).

## 7. Ordem de implementação sugerida (prioridade nos 7 dias)

1. `domain/` completo + testes unitários (state machine, validações, filtro) — **sem UI, sem Qt**
2. `segy_reader.py` + `trace_store.py` streaming, com teste de memória constante
3. `filter_worker.py` + threading básico (sem UI ainda, testar via script simples)
4. UI mínima: 4 telas conectadas aos contratos do domain
5. Persistência de metadados (SQLAlchemy) + histórico funcional
6. Teste E2E completo
7. README com trade-offs
8. Item da trilha de criatividade + demais opcionais, se sobrar tempo
