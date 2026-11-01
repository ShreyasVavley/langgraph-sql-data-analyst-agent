# DataPulse AI: Technical Architecture & Engineering Study Notes
### A Practical Guide to Agentic AI, LangGraph State Machines, and Self-Correcting NL-to-SQL Systems
*Designed for Computer Science, Data Science, and AI Engineering Students*

---

## 📑 Table of Contents
1. [The Core Problem: Why Naive Text-to-SQL Fails](#1-the-core-problem-why-naive-text-to-sql-fails)
2. [Architectural Foundations: Chains vs. State Graphs](#2-architectural-foundations-chains-vs-state-graphs)
3. [System Architecture & State Flow](#3-system-architecture--state-flow)
4. [Component Deep Dive & Code Breakdown](#4-component-deep-dive--code-breakdown)
   - [4.1 Database Layer (`database.py`)](#41-database-layer-databasepy)
   - [4.2 Agentic Core & State Machine (`agent.py`)](#42-agentic-core--state-machine-agentpy)
   - [4.3 Presentation & Interactive Layer (`app.py`)](#43-presentation--interactive-layer-apppy)
5. [The Self-Correction Loop: Anatomy of an Error Recovery](#5-the-self-correction-loop-anatomy-of-an-error-recovery)
6. [Design Patterns & Best Practices Implemented](#6-design-patterns--best-practices-implemented)
7. [Testing & Quality Assurance Suite (`tests/`)](#7-testing--quality-assurance-suite-tests)
8. [Viva & Technical Interview Prep Questions](#8-viva--technical-interview-prep-questions)

---

## 1. The Core Problem: Why Naive Text-to-SQL Fails

When developers first build a "Chat with your Database" tool, they typically use a simple linear prompt chain:

$$\text{User Query} \longrightarrow \text{LLM Prompt} \longrightarrow \text{SQL String} \longrightarrow \text{Database Execution} \longrightarrow \text{Response}$$

### Why this fails in production:
1. **Schema Hallucinations:** LLMs invent table or column names (e.g., using `orders.total_sales` when the schema actually stores `order_items.quantity * order_items.unit_price`).
2. **Dialect Mismatches:** SQLite does not have functions like `DATE_TRUNC()` or `TO_CHAR()`. An LLM without strict constraints might output PostgreSQL or MySQL syntax.
3. **Fragile Failures:** If a generated query throws a `sqlite3.OperationalError`, a linear chain immediately crashes, leaving the user with a broken interface.
4. **Security Vulnerabilities:** An unconstrained text model can generate `DROP`, `DELETE`, or `UPDATE` queries if prompt injected.

### How DataPulse AI Solves This:
By shifting from a **Linear Chain (DAG)** to an **Agentic Cyclic State Graph (LangGraph)** equipped with **Schema Grounding**, **Pydantic Validation**, and a **Self-Correction Feedback Loop**.

---

## 2. Architectural Foundations: Chains vs. State Graphs

| Dimension | Traditional LangChain / LCEL Chain | LangGraph State Machine |
|---|---|---|
| **Graph Topology** | Directed Acyclic Graph (DAG) | Cyclic Graph (supports loops & conditional edges) |
| **State Tracking** | Ephemeral, passed sequentially through pipes `\|` | Centralized, mutable or append-only `AgentState` |
| **Error Handling** | Try/catch blocks outside the LLM flow | In-graph routing nodes that feed errors back to the model |
| **Deterministic Control** | Limited; branching is cumbersome | First-class conditional edges (`should_continue`) |
| **State Inspection** | Opaque intermediate steps | Full inspection of all state transitions and timestamps |

In LangGraph, we define an **`AgentState`** that flows through discrete **Nodes** (Python functions) connected by **Edges** (conditional or direct links).

---

## 3. System Architecture & State Flow

```text
               ┌────────────────────────┐
               │    User Inquiry (NL)   │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ 1. generate_query      │◄── (Database Schema DDL)
               │    (Pydantic Schema)   │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │ 2. execute_query       │
               │    (SQLite Execution)  │
               └─────┬────────────┬─────┘
                     │            │
       [Runtime Error]            [Success]
       & retry < 3   │            │
                     ▼            │
         ┌───────────────────┐    │
         │ 3. self_correct   │    │
         │    (Traceback Fix)│    │
         └───────────┬───────┘    │
                     │            │
                     ▼ (Loop Back)│
               (execute_query)    │
                                  ▼
               ┌────────────────────────┐
               │ 4. synthesize_and_vis  │
               │    (Plotly + Narrative)│
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │  Executive Dashboard   │
               │  - Summary Narrative   │
               │  - KPI Metric Cards    │
               │  - Interactive Chart   │
               │  - Executed SQL        │
               │  - Raw Table Preview   │
               └────────────────────────┘
```

---

## 4. Component Deep Dive & Code Breakdown

### 4.1 Database Layer (`database.py`)

#### Schema Design:
The application models a realistic B2B & Enterprise E-commerce operation with 5 relational tables:
- `categories` $(1:N)$ `products`
- `customers` $(1:N)$ `orders`
- `orders` $(1:N)$ `order_items`
- `products` $(1:N)$ `order_items`

#### Key Engineering Techniques:
1. **Schema Grounding (`get_schema_string`):**
   Extracts `CREATE TABLE` DDL directly from `sqlite_master` along with two real sample rows per table. This ensures the LLM sees exact column types, primary keys, foreign keys, and actual values (e.g. `'Enterprise'` instead of `'B2B'`).
2. **Defensive Security Guardrails (`execute_query`):**
   ```python
   forbidden = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "REPLACE"]
   if first_token in forbidden:
       raise ValueError("Security Alert: Only read-only SELECT queries are allowed.")
   ```
3. **Execution Benchmarking:** Measures query runtime in milliseconds using Python's high-precision `time.perf_counter()`.

---

### 4.2 Agentic Core & State Machine (`agent.py`)

#### The State Definition (`AgentState`):
Using Python's `TypedDict`, the state schema explicitly tracks everything the agent knows:
```python
class AgentState(TypedDict):
    user_query: str
    sql_query: str
    execution_error: Optional[str]
    dataframe_result: Optional[List[Dict[str, Any]]]
    dataframe_columns: Optional[List[str]]
    explanation: Optional[str]
    retry_count: int
    chart_spec: Optional[Dict[str, Any]]
    kpis: Optional[List[Dict[str, Any]]]
    thought_steps: List[Dict[str, Any]]
    execution_time_ms: float
    db_path: str
```

#### Node 1: `generate_query`
- Takes `state["user_query"]` and the extracted SQLite schema.
- Uses `ChatOpenAI.with_structured_output(SQLQueryOutput)` enforcing:
  - `sql_query`: Valid SQLite query string.
  - `query_rationale`: Explanation of joins and aggregations.
  - `tables_used`: List of referenced relations.

#### Node 2: `execute_query`
- Executes `state["sql_query"]` on the database.
- **On Success:** Populates `dataframe_result` and `dataframe_columns`, sets `execution_error = None`.
- **On Failure:** Catches `Exception`, extracts the full Python traceback via `traceback.format_exc()`, and saves it to `state["execution_error"]`.

#### Node 3: `self_correct`
- Triggered exclusively when `execution_error` is not None and `retry_count < 3`.
- Increments `retry_count += 1`.
- Feeds 4 critical pieces of context back to the model:
  1. The original business question.
  2. The database schema DDL.
  3. The exact SQL query that failed.
  4. The runtime error message / traceback.
- Model returns `SQLCorrectionOutput` (`corrected_sql_query`, `error_diagnosis`, `fix_applied`).

#### Node 4: `synthesize_and_visualize`
- Analyzes the resulting tabular dataset.
- In-memory heuristics and LLM synthesis determine:
  - Optimal chart type: **Bar** (categorical comparison), **Line** (chronological dates), **Area** (volume trends), **Scatter** (continuous correlations), or **Pie** (parts of whole $\le 6$).
  - Mapping for X-axis, Y-axis, and color grouping.
  - Generates executive narrative and 2–4 high-level KPI cards.

#### Conditional Routing Edge (`should_continue`):
```python
def should_continue(state: AgentState) -> str:
    if state.get("execution_error") is not None:
        if state.get("retry_count", 0) < 3:
            return "self_correct"       # Loop back to retry
        else:
            return "synthesize_and_visualize"  # Give up gracefully after 3 retries
    return "synthesize_and_visualize"          # Execution succeeded
```

---

### 4.3 Presentation & Interactive Layer (`app.py`)

- **Design Philosophy:** Executive light mode (`#F8FAFC`, slate `#0F172A`, `#334155`, soft borders `#E2E8F0`, indigo/blue `#4F46E5` / `#2563EB`).
- **Collapsible Agent Thought Expander:** Tracks live agent reasoning steps with color-coded status badges:
  - 🟢 Green: Successful execution.
  - 🔴 Red: Intercepted runtime error with expandable stack trace.
  - 🟡 Amber: Self-correction triggered with diagnosis and fix description.
- **4-Tab Executive Results Dashboard:**
  - **Tab 1:** Narrative insights, KPI cards, and responsive Plotly visual.
  - **Tab 2:** Raw tabular data with one-click CSV and JSON exports.
  - **Tab 3:** Verified SQL code block with execution time (ms) and attempt counter.
  - **Tab 4 (Direct SQL Sandbox):** Enables evaluators to write arbitrary SQL to verify calculations independently.

---

## 5. The Self-Correction Loop: Anatomy of an Error Recovery

### Walkthrough of a Real Failure & Recovery Scenario:

#### 1. User Inquiry:
> *"Test self-correction: Select client_name and total sales from client_records"*

#### 2. Initial Query Generated (Node 1):
```sql
SELECT client_name, SUM(order_val) FROM client_records GROUP BY 1;
```

#### 3. Execution Failure (Node 2):
```text
sqlite3.OperationalError: no such table: client_records
```
The state machine intercepts this exception, formats the traceback, and stores it into `state["execution_error"]`.

#### 4. Conditional Edge Evaluation:
`execution_error != None` and `retry_count (0) < 3` $\longrightarrow$ **Route to `self_correct`**.

#### 5. Self-Correction Node (Node 3):
The agent receives the error: `no such table: client_records`. It checks the schema DDL, realizes `customers` holds client names and `orders` + `order_items` hold sales, and writes:
```sql
SELECT c.name AS customer_name, c.segment, ROUND(SUM(oi.total_price), 2) AS total_spend
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.customer_id, c.name, c.segment
ORDER BY total_spend DESC LIMIT 8;
```
`retry_count` becomes `1`.

#### 6. Re-Execution (Node 2):
The corrected query runs cleanly in $4.2\text{ ms}$, retrieving 8 records. `execution_error` is cleared to `None`.

#### 7. Route to Synthesis (Node 4):
The final DataFrame is visualized as a Bar chart with executive business commentary and KPI metrics.

---

## 6. Design Patterns & Best Practices Implemented

1. **State Machine Pattern (`langgraph.graph.StateGraph`):**
   Deconstructs an AI task into explicit state transitions instead of an uncontrolled single-prompt black box.
2. **Circuit Breaker / Retry Limit Pattern:**
   The guard `retry_count < 3` prevents infinite execution loops and runaway API costs.
3. **Structured Outputs Pattern (`pydantic` + `with_structured_output`):**
   Eliminates markdown parsing errors (````sql ... ````) by enforcing schema-validated JSON serialization from the LLM.
4. **Dual-Mode Graceful Degradation:**
   If an OpenAI API key is present, it uses live LLM calls. If absent, it automatically engages an offline deterministic analytical catalog so demonstrations never crash.
5. **Least Privilege Data Access:**
   Enforces read-only SELECT permissions at the application level to prevent destructive SQL operations.

---

## 7. Testing & Quality Assurance Suite (`tests/`)

The repository includes 14 automated unit and integration tests across 3 modules:

| Test File | Focus Area | Key Verifications |
|---|---|---|
| `test_database.py` | Relational Engine & Security | Verifies 5 tables populated; tests foreign key joins; verifies rejection of `DROP`, `DELETE`, `UPDATE` queries. |
| `test_agent.py` | State Graph & Schemas | Validates Pydantic serialization; verifies node contracts; verifies graph compilation. |
| `test_pipeline.py` | End-to-End Integration | Validates standard query execution; tests intentional error self-correction; tests retry cutoff routing. |

Run tests via command line:
```bash
python -m pytest tests -v
```

---

## 8. Viva & Technical Interview Prep Questions

### Q1: Why use LangGraph instead of a standard LangChain SequentialChain?
> **Answer:** Standard LangChain chains are Directed Acyclic Graphs (DAGs) where execution flows in one forward direction. They cannot loop back or make cyclic decisions. LangGraph implements a full State Machine that supports cyclic edges, allowing an agent to fail a step (e.g. SQL syntax error), inspect the failure state, branch to a self-correction node, and loop back to the execution node until success or a retry limit is reached.

### Q2: How does the agent prevent SQL injection or destructive operations?
> **Answer:** Through multi-layer defense:
> 1. *System Prompt Guardrails:* Instructs the LLM to strictly output `SELECT` statements.
> 2. *Application-Level AST/Keyword Filter:* `database.execute_query()` inspects the SQL token stream and throws a `ValueError` if mutating keywords (`DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE`, `ATTACH`) are present.
> 3. *Database Connection Configuration:* SQLite operates with foreign key constraints enabled and read-only query expectations.

### Q3: What is "Schema Grounding" and why is it critical for Text-to-SQL?
> **Answer:** Schema Grounding is the practice of extracting exact DDL statements (`CREATE TABLE`, column types, foreign key relationships) along with representative sample rows from the database engine and injecting them into the LLM's system prompt context. Without this grounding, the LLM hallucinates column and table names based on generic domain knowledge rather than the real database structure.

### Q4: How does the visualization node decide which Plotly chart to render?
> **Answer:** It uses a combination of data type profiling and dimensionality rules:
> - If the X-axis contains datetime/month attributes $\longrightarrow$ **Line / Area Chart** (time series).
> - If discrete categories are compared against a numeric metric $\longrightarrow$ **Bar Chart** (rankings).
> - If comparing two continuous numeric variables $\longrightarrow$ **Scatter Plot** (correlation).
> - If analyzing parts of a whole with $\le 6$ slices $\longrightarrow$ **Pie / Donut Chart** (proportions).
> - If high-cardinality raw text is returned $\longrightarrow$ **Interactive Data Table**.

### Q5: What happens if an error persists after 3 self-correction retries?
> **Answer:** The conditional routing function `should_continue` inspects `retry_count`. Once `retry_count >= 3`, the machine exits the retry loop and routes to `synthesize_and_visualize`. The node gracefully detects the persistent error and presents the user with a transparent diagnosis of why the query could not be resolved, preventing infinite execution and UI crashes.
