# Architectural Design Document / Documento de Diseño Arquitectónico
## LegalMove API - Multi-Agent Contract Comparison System

This document outlines the detailed system flow, structural architecture, security layers, and telemetry design for the **LegalMove API**.

Este documento detalla el flujo del sistema, diseño de arquitectura, capas de seguridad y telemetría de la **LegalMove API**.

---

## 1. Structural Architecture / Resumen de Arquitectura

The LegalMove API uses a layered, asynchronous, service-oriented design. Data flow follows standard constraints to guarantee strict boundary isolation and modular testing.

La API utiliza un diseño en capas y asíncrono. El flujo de datos sigue restricciones estrictas para garantizar el aislamiento de responsabilidades y la facilidad de pruebas.

```mermaid
graph TD
    Client[Client: Postman / Frontend] -->|POST /api/v1/compare| Router[FastAPI Router]
    Router -->|Depends: validate_api_key| SecurityKey[Security Guards Check]
    Router -->|Depends: get_target_language| LangHeader[Language Header Parser]
    
    SecurityKey -->|Validated| Pipeline[Multi-Agent Pipeline Coordinator]
    
    subgraph Multi-Agent Pipeline (app/services/agents.py)
        Pipeline -->|Step 1| VisionAgent[OCR Vision Agent: GPT-4o]
        VisionAgent -->|Raw Extracted Text| ContextAgent[Contextual Mapping Agent]
        ContextAgent -->|Aligned Clauses Index| ExtractionAgent[Extraction & Validation Agent]
    end
    
    ExtractionAgent -->|Structured Output| ValidationGate[Strict Pydantic Validation Gate]
    
    ValidationGate -->|Valid schema: ContractChangeOutput| Router
    ValidationGate -->|Invalid schema: ValueError| SentinelError[Sentinel HTTP 422 Exception]
    
    Router -->|HTTP 200: ContractAnalysisResponse| Client
    SentinelError -->|HTTP 422: Validation Error| Client
```

---

## 2. Multi-Agent Pipeline Stages / Flujo de Agentes del Pipeline

### Step 1: Multimodal Parsing (Vision) / Paso 1: Extracción Multimodal
*   **Engine / Motor:** GPT-4o Vision.
*   **English:** Accepts two Base64 images (original and addendum). Transcribes raw textual contents faithfully, respecting numerical structure and tables.
*   **Español:** Recibe dos imágenes codificadas en Base64. Realiza una transcripción literal y exacta respetando la estructura numérica y de tablas.

### Step 2: Contextual Mapping / Paso 2: Mapeo de Contexto
*   **Engine / Motor:** GPT-4o Text.
*   **English:** Evaluates both transcribed texts and creates a conceptual equivalence map, matching original clauses directly to their updated versions.
*   **Español:** Evalúa ambos textos y crea un mapa conceptual de equivalencias, alineando las cláusulas del contrato original con sus versiones modificadas en la adenda.

### Step 3 & 4: Extraction & Scheme Enforce / Paso 3 y 4: Extracción y Validación
*   **Engine / Motor:** GPT-4o structured output.
*   **English:** Isolates modifications (additions, deletions, edits) using the context map. Enforces output strictly against `ContractChangeOutput` and formats summary fields dynamically in the selected language.
*   **Español:** Aísla las modificaciones usando el mapa de contexto. Fuerza al modelo a devolver el esquema estricto `ContractChangeOutput` y traduce dinámicamente los campos al idioma seleccionado.

---

## 3. Security Architecture / Capas de Seguridad

The API is hardened with five distinct security layers:

La API se encuentra protegida mediante cinco capas de seguridad diferenciadas:

1.  **Base64 Sanitization (Pydantic Gate):** Pre-validates Base64 inputs dynamically to clean headers and reject invalid, empty, or malicious payloads before running any vision steps.
    *   *Sanitización Base64:* Limpia prefijos data-URI y valida la sintaxis de Base64 de forma estricta, rechazando payloads corruptos o vacíos.
2.  **API Key Authorization:** Guards comparison endpoints with an optional, configurable `X-API-Key` HTTP Header.
    *   *Autenticación API Key:* Protege el endpoint con una cabecera de autenticación si está configurada en las variables de entorno.
3.  **HTTP Security Headers:** Injects standard headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`) to block UI attacks.
    *   *Cabeceras Seguras:* Previene Clickjacking, XSS e inyecciones de MIME-types.
4.  **In-Memory Rate Limiting:** Enforces a sliding-window rate limit per client IP to prevent brute-force attacks and API credit abuse.
    *   *Límite de Tasa:* Restringe peticiones sucesivas por dirección IP en el endpoint de comparación.
5.  **Safe CORS Middleware:** Restricts cross-origin requests to explicit allowed domains defined in the environment.
    *   *CORS Restringido:* Evita accesos cruzados no autorizados en entornos de producción.

---

## 4. Observability & Telemetry / Observability y Telemetría

*   **English:** Instrumented natively using Langfuse. Decorators like `@observe()` log execution trace timelines, while LangChain callbacks log token usage and latency metrics per agent.
*   **Español:** Instrumentado nativamente mediante Langfuse. El decorador `@observe()` captura el ciclo de vida del pipeline, y los callbacks de LangChain registran el consumo de tokens y latencias de forma granular.

```
Request POST -> Trace Start -> [ Vision OCR ] -> [ Map Clauses ] -> [ Extract JSON ] -> Trace End -> Response
                                   │                  │                  │
                             (LLM Token)        (LLM Token)        (LLM Token)
```
