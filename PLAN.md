# AI Music Studio — Master Development Prompt

You are the lead engineer and architect responsible for building an AI-native music creation platform.

Your goal is NOT to blindly implement everything at once.

Your responsibility is to:

1. inspect the repository and available environment,
2. research appropriate current technologies only when necessary,
3. design a modular architecture,
4. create a realistic implementation plan,
5. delegate independent work to sub-agents where supported,
6. implement the system incrementally,
7. preserve extensibility for later AI models and editing capabilities,
8. minimize unnecessary tool calls, repeated analysis, verbose reporting, and token usage.

The user will perform runtime testing manually.

Do NOT automatically run tests, builds, development servers, linting, type checking, model inference, benchmarks, or other validation commands unless the user explicitly asks you to do so.

---

# 1. PRODUCT VISION

Build an AI-native music creation studio.

A user should eventually be able to:

- upload multiple reference songs,
- specify what musical characteristics should be taken from each reference,
- describe the desired song using natural language,
- generate original lyrics,
- generate an original composition,
- generate an instrumental arrangement,
- select an independent synthetic AI singer,
- control how that singer performs the song,
- generate vocals,
- automatically mix/master the result,
- manually adjust the generated song,
- selectively regenerate only parts of a song using natural-language instructions.

The product should NOT simply concatenate, remix, or copy uploaded music.

Reference music should primarily be analyzed and transformed into abstract musical characteristics such as:

- rhythm
- BPM
- harmonic characteristics
- instrumentation
- arrangement
- energy curve
- genre
- production characteristics
- atmosphere
- song structure

The resulting composition should be original.

---

# 2. CORE ARCHITECTURAL PRINCIPLE

Separate the system into independent layers.

Conceptually:

Reference Songs
        +
User Prompt
        ↓
REFERENCE ANALYSIS
        ↓
SONG PLANNER / COMPOSER
        ↓
SONG PACKAGE
        ↓
INSTRUMENTAL GENERATION
        +
AI SINGER
        ↓
VOCAL GENERATION
        ↓
MIX / MASTER
        ↓
AI SONG EDITOR

Do NOT tightly couple the entire product to one AI model.

Every major AI capability must be replaceable through an adapter/provider interface.

Examples:

MusicGenerationProvider
VocalSynthesisProvider
LyricsProvider
MusicAnalysisProvider
StemSeparationProvider
MixingProvider

Model-specific code must remain behind these interfaces whenever practical.

---

# 3. REFERENCE MUSIC SYSTEM

Users may upload multiple reference tracks.

Example:

Reference A:
- rhythm: 80%
- energy: 70%

Reference B:
- atmosphere: 90%
- instrumentation: 60%

Reference C:
- harmony: 40%
- production texture: 50%

Analyze each reference independently.

Potential extracted characteristics include:

- BPM
- key
- time signature
- energy curve
- section boundaries
- approximate chord/harmonic information
- instrumentation
- rhythmic density
- spectral/timbral properties
- genre/style descriptors
- arrangement characteristics

Potential technologies include:

- librosa
- Essentia
- Demucs
- appropriate music-information-retrieval models

Do not assume these are final choices.

Research alternatives only when the decision is required for the current phase.

Avoid repeatedly researching decisions that have already been documented.

---

# 4. IMPORTANT VOCAL RULE

Reference-song vocals must NOT define the identity of the generated singer.

We explicitly do NOT want to clone the singer contained in a reference track.

Reference tracks are composition/production references.

Singer identity belongs to a completely separate subsystem.

Where useful, perform stem separation and remove/isolate reference vocals before passing audio to models whose reference conditioning could accidentally capture vocal identity.

The architecture must make this separation explicit.

---

# 5. SONG PACKAGE

Composition must NOT exist only as a rendered WAV file.

Create a structured intermediate representation called:

SongPackage

It should eventually contain:

- metadata
- duration
- BPM
- key
- time signature
- lyrics
- song sections
- vocal melody
- notes
- note timing
- syllable/phoneme alignment where available
- chord progression
- arrangement information
- performance instructions
- MIDI or equivalent symbolic representations
- instrumental stems
- generated vocals
- mix information

Possible conceptual representation:

project/
  song.json
  lyrics.json
  sections.json
  chords.json

  midi/
    vocal.mid
    chords.mid
    arrangement.mid

  stems/
    drums.wav
    bass.wav
    guitar.wav
    piano.wav
    synth.wav
    other.wav

  vocals/
    lead.wav
    harmony.wav
    adlibs.wav

  mix/
    final.wav

This exact filesystem structure is NOT mandatory.

Design an appropriate domain model first.

The important requirement is that the composition remains editable and machine-readable.

---

# 6. SONGWRITER / COMPOSITION SYSTEM

The composition system receives:

- reference analysis,
- reference weighting,
- user prompt,
- desired duration,
- optional genre,
- optional language,
- optional lyrical concept,
- optional structural requirements.

It should produce a SongPackage or intermediate SongPlan.

The composition stage should handle:

- lyrics
- structure
- vocal melody
- harmony/chords
- BPM
- key
- arrangement plan
- instrumentation
- energy progression

Example:

Intro
Verse 1
Pre-Chorus
Chorus
Verse 2
Chorus
Bridge
Final Chorus
Outro

Do not rely exclusively on generated audio to infer these elements afterward.

Whenever practical, create symbolic composition information before final rendering.

---

# 7. INSTRUMENTAL GENERATION

The instrumental generator converts the composition into audio.

Investigate current open-source/local music-generation models when this phase is reached.

ACE-Step or its current successor/version may be considered, but do NOT blindly assume a particular version or repository remains the best choice.

Verify when required:

- project status
- license
- hardware requirements
- inference capabilities
- duration limitations
- reference-audio support
- instrumental generation
- controllability
- stem capabilities
- MIDI/symbolic conditioning

The architecture must allow replacement of the music-generation model later.

Prefer generating or retaining stems whenever practical.

---

# 8. AI SINGER SYSTEM

Singer identity must be independent from composition.

Conceptually:

SongPackage
    +
SingerProfile
    +
PerformancePrompt
        ↓
Vocal Synthesis
        ↓
Dry Vocal

A SingerProfile may describe:

Identity:
- synthetic singer ID
- voice embedding/model reference

Voice characteristics:
- vocal range
- brightness
- warmth
- breathiness
- raspiness
- airiness
- vocal weight
- register characteristics

Technique:
- chest voice
- mixed voice
- head voice
- falsetto
- belt
- vibrato tendencies

The singer must be reusable.

For example:

Song A + Singer Luna
Song A + Singer Noah
Song A + Singer Rin
Song B + Singer Luna

must be possible without recomposing the song.

Investigate Singing Voice Synthesis rather than assuming ordinary voice conversion is sufficient.

Potential technologies include:

- DiffSinger-family systems
- modern SVS models
- phoneme-based singing synthesis
- MIDI-conditioned singing synthesis

Research the current ecosystem when this phase is reached.

---

# 9. PERFORMANCE CONTROL

Singer identity and performance must remain separate.

Example:

Singer:
LUNA

Verse:
- intimate
- soft
- breathy
- restrained vibrato

Chorus:
- powerful
- emotional
- stronger chest/mixed voice

Final Chorus:
- maximum energy
- sustained notes
- optional ad-libs

Eventually support instructions such as:

"Sing the verse softly and intimately, gradually increase intensity, then deliver the final chorus with strong emotional belting."

If the selected model cannot directly understand these instructions, design an intermediate parameter-mapping layer.

---

# 10. MIXING AND MASTERING

Keep instrumental and vocal stems separate whenever possible.

Support eventually:

- volume
- pan
- EQ
- compression
- reverb
- delay
- vocal placement
- limiting
- loudness normalization

Do not destroy source stems after mixing.

Conceptually:

instrumental stems
        +
lead vocal
        +
harmonies
        +
ad-libs
        ↓
mixing
        ↓
mastering
        ↓
final.wav

Automated mixing may initially be simple and deterministic.

Advanced AI-assisted mixing can be added later.

---

# 11. AI SONG EDITOR

The long-term product should contain a lightweight AI-native DAW/editor.

Do NOT attempt to recreate Ableton, Logic, FL Studio, or Pro Tools.

Focus specifically on editing AI-generated songs.

Timeline concept:

Vocals   ███████████████████
Drums    ███████████████████
Bass     ███████████████████
Guitar   ███████████████████
Synth    ███████████████████

Users should eventually be able to select a region.

Example:

Selected:
Vocals
01:12–01:28

Prompt:

"Sing this section more emotionally and hold the final note longer."

Expected behavior:

- preserve instrumental,
- preserve singer identity,
- preserve lyrics unless requested otherwise,
- preserve melody unless requested otherwise,
- regenerate only the selected vocal region,
- merge the regenerated region cleanly.

---

# 12. EDITING CAPABILITIES

Design toward eventual support for:

## Mixing

- volume
- pan
- mute
- solo
- EQ
- compression
- reverb
- delay

## Vocal editing

- selected-region regeneration
- emotional intensity
- breathiness
- vibrato
- vocal power
- articulation
- sustained-note duration
- octave/register changes
- ad-libs

## Melody editing

Eventually provide a piano-roll-like representation.

Changing individual notes should allow affected vocal regions to be regenerated.

## Lyrics editing

Changing lyrics should allow only affected vocal segments to be regenerated.

## Instrument editing

Example:

"Make the guitar solo between 2:10 and 2:30 faster and more aggressive."

Only the affected instrument/range should be regenerated where supported.

## Arrangement editing

Eventually support:

- shorten intro
- repeat chorus
- remove bridge
- extend outro
- insert drum fill
- regenerate section

---

# 13. NON-DESTRUCTIVE EDITING

Editing should be non-destructive whenever practical.

Think in terms of:

Project
→ SongPackage
→ revisions

instead of repeatedly overwriting a final WAV.

Track where practical:

- source asset
- generated asset
- generation parameters
- model/provider
- seed
- affected time range
- prompt
- previous version

Users should eventually be able to undo edits or regenerate them.

---

# 14. ORIGINALITY AND REFERENCE SAFETY

The product is intended to generate new music inspired by abstract characteristics of reference tracks, not reproduce recordings.

Design toward:

- melody similarity detection
- audio fingerprint comparison
- excessive reference similarity detection
- configurable similarity thresholds
- warnings/re-generation for suspicious similarity

Do not make false guarantees of copyright safety.

Document technical limitations.

Singer creation should focus on synthetic/original or appropriately authorized voices rather than assuming arbitrary real-person voice cloning.

---

# 15. TECHNOLOGY DIRECTION

Preferred initial architecture:

Frontend:
- SvelteKit
- TypeScript

Backend:
- Python
- FastAPI

AI:
- PyTorch
- model-specific libraries

Audio:
- FFmpeg
- librosa / Essentia or alternatives

Storage:
- local storage initially
- object-storage abstraction later

Database:
- PostgreSQL

Background processing:
- asynchronous GPU jobs

These choices are not immutable.

If repository constraints or current technology strongly justify an alternative, explain the reason concisely before changing a core technology.

---

# 16. GPU JOB ARCHITECTURE

Do not design expensive music generation as a normal synchronous HTTP operation.

Use a job abstraction.

Example:

POST /projects/{id}/generate
        ↓
GenerationJob
        ↓
Queue
        ↓
GPU Worker
        ↓
Progress
        ↓
Result assets

Possible states:

queued
preparing
running
postprocessing
completed
failed
cancelled

Local development may initially execute jobs simply while preserving the ability to introduce distributed GPU workers later.

---

# 17. MULTI-AGENT WORKFLOW

Use sub-agents only where parallel work provides meaningful value.

Suggested roles:

## Architecture Agent

- repository inspection
- domain model
- module boundaries
- API design
- SongPackage
- job architecture

## Music AI Agent

Research when needed:

- music generation
- reference conditioning
- symbolic composition
- MIDI generation
- stem generation
- hardware requirements
- licensing

## Vocal/SVS Agent

Research when needed:

- singing voice synthesis
- MIDI-conditioned vocals
- phoneme alignment
- reusable synthetic singer identity
- performance control
- training/fine-tuning

## Audio/DSP Agent

Own:

- FFmpeg pipeline
- normalization
- stems
- mixing
- crossfades
- region replacement
- waveform metadata

## Frontend Agent

Own:

- project UI
- uploads
- reference weighting
- generation UI
- editor/timeline
- waveform visualization

## Backend Agent

Own:

- FastAPI
- persistence
- project API
- asset API
- generation jobs
- provider interfaces

## Reviewer Agent

Review only when useful.

Focus on:

- architecture violations
- broken interfaces
- security problems
- duplicated abstractions
- model coupling
- obvious implementation mistakes

Do NOT create agents merely to demonstrate multi-agent usage.

Prefer fewer agents when the task is small.

---

# 18. AGENT COORDINATION

Before parallel implementation:

1. establish shared interfaces,
2. establish data contracts,
3. delegate independent modules,
4. integrate results.

Maintain useful documentation such as:

docs/
  ARCHITECTURE.md
  SONG_PACKAGE.md
  AI_PROVIDERS.md
  API.md
  DEVELOPMENT.md
  ROADMAP.md

Do not create documentation merely to repeat information already contained elsewhere.

If an architectural assumption becomes invalid, update the appropriate documentation instead of silently introducing a workaround.

---

# 19. TESTING AND VALIDATION POLICY

The USER is responsible for runtime testing and validation.

This rule exists to reduce unnecessary compute and token usage.

Unless the user explicitly requests testing, DO NOT automatically run:

- unit tests,
- integration tests,
- end-to-end tests,
- frontend tests,
- backend tests,
- pytest,
- Vitest,
- Playwright,
- Cypress,
- lint,
- ESLint,
- Ruff,
- formatting checks,
- type checking,
- TypeScript checks,
- builds,
- production builds,
- development servers,
- preview servers,
- Docker builds,
- model inference,
- GPU inference,
- benchmarks,
- audio generation tests,
- browser automation,
- API smoke tests.

Do NOT repeatedly execute commands merely to "make sure" something works.

You may inspect code statically and reason about correctness.

You may create or update tests if doing so is specifically useful for the implementation, but DO NOT execute them unless explicitly requested.

When completing a task, provide only the minimal manual verification instructions necessary for the user.

Example:

Manual verification:
1. Start backend: `...`
2. Start frontend: `...`
3. Open `...`
4. Verify that `...`

Keep manual verification instructions concise.

If the user reports an error from their manual testing:

1. analyze the provided error,
2. inspect the relevant code,
3. implement the likely fix,
4. tell the user what to retest.

Do not independently run the application afterward unless explicitly requested.

---

# 20. TOKEN AND COMPUTE EFFICIENCY

Token efficiency is an explicit project requirement.

Avoid:

- unnecessarily verbose status reports,
- repeating the task back to the user,
- repeatedly summarizing AGENTS.md,
- re-reading large files when only a small section is relevant,
- repeated repository-wide searches,
- repeated web research,
- unnecessary sub-agents,
- asking agents to investigate the same problem independently without reason,
- generating large speculative documents,
- running validation commands automatically,
- explaining obvious code changes line by line.

Prefer:

- targeted repository inspection,
- targeted file reads,
- concise implementation,
- parallel agents only for genuinely independent work,
- reusing documented decisions,
- small focused edits,
- short completion reports.

When reporting completion, normally provide only:

- what changed,
- important decisions or limitations,
- files/modules affected,
- what the user should manually verify next.

Do not provide lengthy retrospectives unless requested.

---

# 21. OBSERVABILITY

Generation failures must eventually be diagnosable.

Log useful metadata such as:

- job ID
- project ID
- provider
- model
- generation stage
- duration
- error category

Avoid logging uploaded audio contents or unnecessary private information.

Preserve model parameters and generation metadata required for reproducibility.

---

# 22. SECURITY

Treat uploaded media as untrusted.

Validate:

- MIME type
- extension
- file size
- decoded audio format
- duration

Do not construct shell commands through unsafe string concatenation.

Use safe subprocess invocation for FFmpeg.

Prevent path traversal.

Keep project assets isolated.

Never expose arbitrary filesystem paths through APIs.

---

# 23. DEVELOPMENT PHASES

Do NOT implement the entire vision at once.

## Phase 0 — Research & Architecture

Produce:

- repository assessment
- architecture
- technology evaluation
- domain model
- SongPackage specification
- provider interfaces
- API proposal
- roadmap
- major technical risks

STOP after Phase 0.

Do NOT automatically continue to Phase 1.

Wait for explicit user instruction.

## Phase 1 — Application Skeleton

Build:

- SvelteKit frontend
- FastAPI backend
- project creation
- reference uploads
- asset storage
- database schema
- generation-job abstraction
- fake AI providers

Goal:

The application workflow should be structurally implemented without requiring real AI inference.

STOP when Phase 1 implementation is complete.

Do NOT automatically run tests or builds.

Provide concise manual verification instructions and wait for the user.

## Phase 2 — Reference Analysis

Add:

- audio metadata extraction
- BPM/key analysis
- reference characteristics
- stem separation where useful
- reference weighting

STOP after implementation and wait for user verification.

## Phase 3 — Composition

Add:

- SongPlan
- lyrics
- structure
- harmony
- vocal melody representation
- symbolic music representation

STOP after implementation and wait for user verification.

## Phase 4 — Instrumental Generation

Integrate the selected music-generation provider.

Preserve provider abstraction.

STOP after implementation and wait for user verification.

## Phase 5 — AI Singer

Integrate the selected SVS system.

Support:

SongPackage
+
SingerProfile
+
Performance configuration
→
dry vocal

STOP after implementation and wait for user verification.

## Phase 6 — Mix / Master

Combine stems and vocals.

Produce final songs while retaining source stems.

STOP after implementation and wait for user verification.

## Phase 7 — Editor

Add:

- waveform/timeline
- stems
- volume/pan
- mute/solo
- basic effects
- region selection

STOP after implementation and wait for user verification.

## Phase 8 — AI Editing

Add targeted regeneration where supported:

- vocal-region regeneration
- lyrics replacement
- melody edits
- instrument-region regeneration
- arrangement edits

STOP after implementation and wait for user verification.

---

# 24. INITIAL TASK

When this AGENTS.md is first introduced:

1. inspect the repository,
2. identify what already exists,
3. perform only research required for Phase 0,
4. use research/architecture sub-agents only where useful,
5. define the architecture,
6. define SongPackage,
7. define provider interfaces,
8. define the initial API,
9. identify major technical risks,
10. create the roadmap.

Complete Phase 0 only.

DO NOT begin Phase 1 automatically.

DO NOT run tests, builds, linting, type checking, development servers, model inference, or benchmarks.

Report the Phase 0 result concisely and wait for explicit user instruction.

---

# 25. ENGINEERING RULES

Throughout development:

- inspect before editing,
- do not rewrite working code without reason,
- prefer small cohesive modules,
- avoid premature abstraction except around AI providers and core domain boundaries,
- prevent model-specific logic from leaking into domain code,
- validate important assumptions through documentation or targeted investigation,
- do not silently ignore errors,
- preserve existing user work,
- keep migrations reproducible,
- keep APIs typed,
- document major architectural decisions,
- keep secrets out of source control,
- never commit model weights,
- never commit generated multi-GB audio artifacts,
- keep expensive AI inference optional,
- do not run tests or validation commands unless explicitly requested,
- let the user perform runtime verification,
- optimize tool calls and responses for token efficiency.

Do not claim that runtime behavior has been tested if it has not been tested.

Instead say:

"Implemented; runtime verification remains for the user."

When an implementation decision is uncertain:

1. investigate only what is necessary,
2. compare realistic options,
3. choose the simplest solution preserving required extensibility,
4. document the decision concisely.

Do not overengineer hypothetical scalability problems before the basic product works.

At the same time, do not make shortcuts that fundamentally prevent:

- multiple reference tracks,
- interchangeable AI models,
- reusable singers,
- stem-based editing,
- partial regeneration,
- non-destructive editing.

---

# 26. DEFINITION OF THE PRODUCT

Always preserve this conceptual separation:

REFERENCE
"What should inspire the composition?"

COMPOSITION
"What is the song?"

INSTRUMENTAL
"How does the music sound?"

SINGER
"Who is singing?"

PERFORMANCE
"How are they singing this particular song?"

MIX
"How do all tracks fit together?"

EDITOR
"What should the user change?"

These concepts must not collapse into one opaque generation call.

The long-term goal is not merely an AI song generator.

The goal is an:

**AI-native music production environment where generation remains editable.**