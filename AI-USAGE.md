# AI Usage

## Development-time assistance

AI/Codex was used as a development assistant during the implementation of THE
GROUNDED. Assistance was provided within explicitly defined step scopes for
source analysis, ingestion, retrieval, temporal applicability, evidence
assessment, question analysis, decision gating, answer generation, pipeline
integration, public interface work, audit logging, evaluation, CLI work, the
Step 15 artifact/store layer, deterministic calculation work, structured
presentation, audit completeness, and documentation refresh.

AI assistance included reading repository materials, proposing and writing
implementation changes, adding tests and inspection scripts, reviewing
interfaces, and helping identify compatibility issues. The current documents
record architectural rationale and development process; they are not claims
that AI independently established policy correctness.

## Human responsibility

The project requirements and step boundaries were defined by the developer.
The developer is responsible for reviewing changes, deciding which changes
are accepted, running the test and inspection commands, reviewing their
results, and deciding what is committed or pushed.

AI-generated or AI-assisted code was validated using the repository's
deterministic unit, integration, CLI, artifact, and inspection tests. Passing
tests demonstrate that the implemented behavior matches the encoded
expectations; they do not independently prove that the supplied policy is
legally or administratively correct.

## Runtime behavior

Development-time AI assistance is separate from runtime system behavior. The
current runtime does not call OpenAI, another LLM, a model API, a web service,
or an external knowledge source. Runtime behavior is implemented with local
Python code, deterministic lexical retrieval, explicit temporal rules,
structured evidence and decision gates, local audit logging, and local
evaluation.

## Policy authority and derived artifacts

The supplied original policy manual and amendment source files remain the
authoritative policy inputs. The system preserves their provision and
amendment provenance and does not treat AI-generated text as policy authority.

Step 15 build artifacts—provision JSON, amendment JSON, the manifest, and the
lexical search index—are deterministic data derived from those source files.
They are reproducible build outputs, not independent policy documents. The
offline artifact loader validates amendment targets and `old_text` integrity
before accepting the stored records.

## Privacy and security boundary

No private prompts, credentials, personal information, or conversation
transcripts are included in this document. AI was not used as a runtime user
data processor. Local audit files may contain execution information when a
caller explicitly enables audit logging; their handling remains the
responsibility of the project operator.

## Limitations

AI assistance did not replace human review of policy meaning. Features that
remain planned or partial, such as general award calculations, unrestricted
semantic claim validation, conversational refusal prose, and packaging should
not be inferred from this document as current runtime capabilities. Step 25
final hardening and final repository verification are complete; the known
Windows temporary-directory permission limitation remains an environment
constraint rather than an application capability.
