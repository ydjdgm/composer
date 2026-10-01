<script lang="ts">
  import { api, features, type Reference, type Weights } from './api';
  let { reference, save }: { reference: Reference; save: (reference: Reference, weights: Weights) => Promise<void> } = $props();
  let draft = $state<Weights>({ ...reference.weights });
  let busy = $state(false);
  let error = $state('');
  let dirty = $state(false);
  $effect(() => { if (!dirty) draft = { ...reference.weights }; });
  async function submit() {
    busy = true; error = '';
    try { await save(reference, { ...draft }); dirty = false; }
    catch (cause) { error = cause instanceof Error ? cause.message : '가중치를 저장하지 못했습니다.'; }
    finally { busy = false; }
  }
</script>

<article class="reference-card">
  <div class="row"><strong class="truncate">{reference.label}</strong><span class:ready={reference.validation_state === 'ready'} class="badge">{reference.validation_state === 'ready' ? '사용 가능' : reference.validation_state === 'pending' ? '검증 대기' : '파일 거절됨'}</span></div>
  {#if reference.error}<p class="error" role="status">{reference.error.message}</p>{/if}
  {#if reference.validation_state === 'ready'}
    <div class="reference-audio"><p class="muted small">업로드한 원본 참조곡 {reference.audio_metadata ? `· ${Math.round(reference.audio_metadata.duration_seconds)}초` : ''}</p><audio controls preload="none" src={api.referenceContent(reference)} aria-label={`${reference.label} 원본 참조곡 재생`}></audio></div>
  {/if}
  <details>
    <summary>참조 특성 가중치 <small>v{reference.version}</small></summary>
    <div class="weights">
      {#each Object.entries(features) as [key, label]}
        <label>{label}<output>{Math.round((draft[key as keyof Weights] ?? 0) * 100)}%</output>
          <input type="range" min="0" max="1" step="0.05" bind:value={draft[key as keyof Weights]} oninput={() => dirty = true} disabled={busy} />
        </label>
      {/each}
    </div>
    <p class="muted small">Phase 1에서는 설정만 저장합니다. 실제 음악 분석은 아직 제공하지 않습니다.</p>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <button class="secondary" onclick={submit} disabled={busy || !dirty}>{busy ? '저장 중…' : '가중치 저장'}</button>
  </details>
</article>
