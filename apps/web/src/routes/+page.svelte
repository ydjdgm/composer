<script lang="ts">
  import { onMount } from 'svelte';
  import { api, active, ApiError, type Project, type Reference, type Job, type Revision, type GenerateRequest, type Weights } from '$lib/api';
  import ReferenceCard from '$lib/ReferenceCard.svelte';
  import './studio.css';

  let projects = $state<Project[]>([]), project = $state<Project | null>(null);
  let references = $state<Reference[]>([]), jobs = $state<Job[]>([]), revisions = $state<Revision[]>([]);
  let snapshot = $state<Record<string, unknown> | null>(null);
  let title = $state(''), newBrief = $state(''), prompt = $state('');
  let duration = $state(120), language = $state('ko'), genre = $state('');
  let error = $state(''), busy = $state(false), loading = $state(true), uploading = $state(false);
  let nextCursor = $state<string | null>(null);
  let pendingRequest = $state<{ projectId: string; key: string; body: GenerateRequest } | null>(null);
  let revisionLoading = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let epoch = 0, revisionEpoch = 0, refreshSequence = 0, disposed = false;
  const states: Record<string, string> = { queued: '대기 중', preparing: '준비 중', running: '진행 중', postprocessing: '마무리 중', completed: '완료', failed: '실패', cancelled: '취소됨' };
  const message = (cause: unknown) => cause instanceof Error ? cause.message : '요청에 실패했습니다.';
  const date = (value: string) => new Date(value).toLocaleString('ko-KR');
  const running = $derived(jobs.filter(active));

  function schedule(id: string, token: number) {
    clearTimeout(timer);
    if (!disposed && token === epoch && (jobs.some(active) || references.some(reference => reference.validation_state === 'pending'))) {
      timer = setTimeout(() => refresh(id, token), 1500);
    }
  }
  async function refresh(id = project?.id, token = epoch) {
    if (!id || token !== epoch || disposed || id !== project?.id) return;
    const sequence = ++refreshSequence;
    clearTimeout(timer);
    try {
      // Poll known active jobs individually as well so old work cannot disappear behind pagination.
      const tracked = jobs.filter(active);
      const [p, r, j, v, activeJobs, trackedJobs] = await Promise.all([api.project(id), api.references(id), api.jobs(id), api.revisions(id), api.activeJobs(id), Promise.all(tracked.map(job => api.job(id, job.id)))]);
      if (token !== epoch || sequence !== refreshSequence || disposed) return;
      project = p; references = r.items;
      jobs = [...new Map([...activeJobs, ...j.items, ...trackedJobs].map(job => [job.id, job])).values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
      revisions = v.items;
      projects = projects.map(item => item.id === p.id ? p : item);
      schedule(id, token);
    } catch (cause) { if (token === epoch && sequence === refreshSequence) error = `${message(cause)} 새로고침으로 다시 연결할 수 있습니다.`; }
  }
  async function select(p: Project) {
    clearTimeout(timer); const token = ++epoch; revisionEpoch++;
    project = p; references = []; jobs = []; revisions = []; snapshot = null; revisionLoading = false;
    prompt = p.brief; pendingRequest = null; error = ''; loading = true;
    await refresh(p.id, token);
    if (token === epoch) loading = false;
  }
  async function loadProjects(more = false) {
    loading = true; error = '';
    try {
      const result = await api.projects(more ? nextCursor ?? undefined : undefined);
      projects = more ? [...projects, ...result.items] : result.items; nextCursor = result.next_cursor;
      if (!project && projects.length) await select(projects[0]);
    } catch (cause) { error = message(cause); }
    finally { loading = false; }
  }
  onMount(() => { void loadProjects(); return () => { disposed = true; epoch++; clearTimeout(timer); }; });
  async function create(event: SubmitEvent) {
    event.preventDefault(); busy = true; error = '';
    try { const p = await api.createProject(title.trim(), newBrief.trim()); projects = [p, ...projects]; title = ''; newBrief = ''; await select(p); }
    catch (cause) { error = message(cause); } finally { busy = false; }
  }
  async function upload(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const files = Array.from(input.files ?? []); input.value = '';
    if (!project || !files.length) return;
    const id = project.id, token = epoch; uploading = true; error = '';
    const failures: string[] = [];
    for (const file of files) {
      try { await api.upload(id, file); }
      catch (cause) { failures.push(`${file.name}: ${message(cause)}`); }
    }
    if (token === epoch) { await refresh(id, token); if (failures.length) error = failures.join('\n'); }
    uploading = false;
  }
  async function saveWeights(reference: Reference, weights: Weights) {
    if (!project) return;
    const id = project.id, token = epoch;
    try {
      const updated = await api.weights(id, reference, weights);
      if (token === epoch) references = references.map(r => r.id === updated.id ? updated : r);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        await refresh(id, token);
        throw new Error('다른 변경이 먼저 저장되었습니다. 현재 가중치를 확인한 뒤 다시 저장하세요.');
      }
      throw cause;
    }
  }
  async function generate(event?: SubmitEvent) {
    event?.preventDefault(); if (!project) return;
    busy = true; error = ''; const token = epoch;
    const request = pendingRequest ?? {
      projectId: project.id, key: crypto.randomUUID(),
      body: { kind: 'mock_song' as const, base_revision_id: project.head_revision_id,
        reference_ids: references.filter(r => r.validation_state === 'ready').map(r => r.id),
        brief: { prompt: prompt.trim(), duration_seconds: duration, language, genre: genre.trim() || null }, seed: null }
    };
    pendingRequest = request;
    try {
      const job = await api.generate(request.projectId, request.body, request.key);
      if (token !== epoch) return;
      pendingRequest = null; jobs = [job, ...jobs.filter(item => item.id !== job.id)];
      await refresh(request.projectId, token);
    } catch (cause) {
      if (token === epoch) {
        error = message(cause);
        // Keep the same request/key after network or server errors; retries cannot enqueue duplicate work.
        if (cause instanceof ApiError && cause.status < 500) { pendingRequest = null; await refresh(request.projectId, token); }
      }
    } finally { busy = false; }
  }
  async function cancel(job: Job) {
    const token = epoch; error = '';
    try { await api.cancel(job.project_id, job.id); await refresh(job.project_id, token); }
    catch (cause) { if (token === epoch) error = message(cause); }
  }
  async function showRevision(id: string) {
    if (!project) return;
    const token = ++revisionEpoch; revisionLoading = true; error = '';
    try { const value = await api.revision(project.id, id); if (token === revisionEpoch) snapshot = value; }
    catch (cause) { if (token === revisionEpoch) error = message(cause); }
    finally { if (token === revisionEpoch) revisionLoading = false; }
  }
</script>

<svelte:head><title>Composer — AI Music Studio</title><meta name="description" content="레퍼런스에서 시작하는 나만의 음악 작업실. Phase 1 로컬 스튜디오." /></svelte:head>

<div class="studio">
  <aside class="sidebar">
    <a class="brand" href="/" aria-label="Composer 홈"><span class="brand-icon">c</span>composer<span class="brand-dot">.</span></a>
    <div class="workspace-label">LOCAL WORKSPACE <span class="status-dot"></span></div>
    <div class="sidebar-heading"><h2>프로젝트</h2><span>{projects.length}</span></div>
    <nav aria-label="프로젝트 목록">
      {#each projects as item}
        <button class:chosen={project?.id === item.id} class="project-button" onclick={() => select(item)} disabled={busy || uploading}><span class="project-icon">♫</span><span class="truncate">{item.title}</span></button>
      {/each}
      {#if !projects.length && !loading}<p class="muted small">첫 프로젝트를 만들어 보세요.</p>{/if}
    </nav>
    {#if nextCursor}<button class="text-button" onclick={() => loadProjects(true)} disabled={loading}>더 보기</button>{/if}
    <form class="new-project" onsubmit={create}>
      <h3>새로운 아이디어</h3>
      <label for="title" class="sr-only">프로젝트 이름</label><input id="title" bind:value={title} maxlength="160" required placeholder="프로젝트 이름" />
      <label for="new-brief" class="sr-only">프로젝트 설명</label><textarea id="new-brief" bind:value={newBrief} rows="2" maxlength="4000" placeholder="어떤 곡을 만들고 싶나요? (선택)"></textarea>
      <button class="secondary full" disabled={busy || uploading || !title.trim()}>＋ 프로젝트 만들기</button>
    </form>
    <div class="sidebar-footer"><span class="badge">PHASE 01</span><p>아이디어를 위한 공간.<br />음악을 위한 새로운 시작.</p></div>
  </aside>

  <main>
    <header class="topbar"><span>작업실 <span class="slash">/</span> {project?.title ?? '시작하기'}</span><span class="badge mock">FAKE PROVIDER</span></header>
    <div class="content">
      <div class="heading-row"><div><p class="eyebrow">YOUR NEXT SOUND STARTS HERE</p><h1>{project?.title ?? '새로운 음악의 시작'}</h1><p class="muted">레퍼런스를 모으고, 다음 곡의 방향을 정해 보세요.</p></div><button class="secondary" onclick={() => project ? refresh() : loadProjects()} disabled={loading || busy || uploading}>↻ 새로고침</button></div>
      <div class="notice"><span>◈</span><div><strong>지금은 스튜디오의 뼈대를 만드는 단계입니다.</strong><p>업로드와 작업 흐름을 사용할 수 있습니다. 생성 결과는 모의 SongPackage이며, 실제 음악 분석·오디오·가창은 생성하지 않습니다.</p></div></div>
      {#if error}<div class="error global-error" role="alert">{error}</div>{/if}
      {#if loading}<p class="muted" role="status">작업실을 불러오는 중…</p>{/if}
      {#if project}
        <div class="columns">
          <section class="panel references"><div class="panel-heading"><div><span class="step">01</span><h2>영감의 출발점</h2></div><span class="muted small">{references.length}개 레퍼런스</span></div>
            <p class="muted">참조곡의 리듬, 분위기, 악기 구성을 바탕으로 방향을 설정하세요. 가수의 목소리는 참조하지 않습니다.</p>
            <label class="upload-zone" class:disabled={uploading || loading}><span class="upload-icon">↑</span><strong>{uploading ? '파일을 업로드하는 중…' : '레퍼런스 오디오 추가'}</strong><span>여러 파일 선택 · WAV, MP3, FLAC</span><small>기본 제한: 파일당 100 MiB · 10분 · 프로젝트당 10개</small><input type="file" multiple accept=".wav,.mp3,.flac,audio/wav,audio/mpeg,audio/flac" onchange={upload} disabled={uploading || loading || busy} /></label>
            <div class="reference-list">{#each references as reference (reference.id)}<ReferenceCard {reference} save={saveWeights} />{/each}</div>
            {#if !references.length}<p class="empty-text">레퍼런스 없이 프롬프트만으로도 시작할 수 있습니다.</p>{/if}
          </section>
          <section class="panel"><div class="panel-heading"><div><span class="step">02</span><h2>곡의 방향</h2></div><span class="badge">MOCK</span></div>
            <form onsubmit={generate}>
              <label for="prompt">어떤 음악을 상상하나요?</label><textarea id="prompt" class="prompt" rows="6" bind:value={prompt} required maxlength="8000" disabled={!!pendingRequest} placeholder="늦은 밤 도시를 걷는 느낌. 부드러운 신스와 따뜻한 베이스, 차분한 벌스에서 힘찬 후렴으로 이어지는 곡."></textarea>
              <div class="form-grid"><div><label for="duration">목표 길이 (초)</label><input id="duration" type="number" min="1" max="600" step="1" bind:value={duration} required disabled={!!pendingRequest} /></div><div><label for="language">언어</label><select id="language" bind:value={language} disabled={!!pendingRequest}><option value="ko">한국어</option><option value="en">English</option><option value="ja">日本語</option></select></div></div>
              <label for="genre">장르 <span class="muted">선택</span></label><input id="genre" bind:value={genre} maxlength="100" disabled={!!pendingRequest} placeholder="예: Indie pop, Ambient" />
              <p class="muted small">검증 완료 레퍼런스 {references.filter(r => r.validation_state === 'ready').length}개와 저장된 가중치를 사용합니다.</p>
              <button class="primary full" disabled={busy || loading || uploading || (!pendingRequest && !prompt.trim())}>{busy ? '요청 중…' : pendingRequest ? '동일한 생성 요청 다시 보내기' : '✦ 모의 생성 시작'}</button>
              {#if pendingRequest}<p class="small muted">응답이 확인되지 않았습니다. 재시도는 동일한 요청을 사용해 중복 생성을 방지합니다.</p>{/if}
            </form>
          </section>
        </div>
        <section class="panel job-panel"><div class="panel-heading"><div><span class="step">03</span><h2>작업과 결과</h2></div><span class="muted small">{running.length ? `${running.length}개 진행 중 · 자동 갱신` : '진행 중인 작업 없음'}</span></div>
          {#if !jobs.length}<div class="empty-state"><span>♫</span><h3>첫 번째 아이디어를 기다리고 있어요.</h3><p class="muted">모의 생성을 시작하면 작업 상태와 revision이 여기에 나타납니다.</p></div>{/if}
          <div class="jobs">{#each jobs as job (job.id)}<article class="job"><div class="row"><div><strong>{job.kind === 'mock_song' ? 'SongPackage 모의 생성' : '참조 파일 검증'}</strong> <span class="badge">{states[job.state] ?? job.state}</span></div>{#if active(job)}<button class="text-button" onclick={() => cancel(job)} disabled={!!job.cancel_requested_at}>{job.cancel_requested_at ? '취소 요청됨' : '취소'}</button>{/if}</div><p class="muted small">{date(job.created_at)} · {job.stage}</p>{#if job.progress !== null}<progress value={job.progress} max="1" aria-label="작업 진행률"></progress>{/if}{#if job.error}<p class="error">{job.error.message}</p>{/if}{#if job.needs_review}<p class="review-note">다른 revision 이후 완료된 결과입니다. 현재 head를 변경하지 않고 별도 보존했습니다.</p>{/if}{#if job.result_revision_id}<button class="text-button accent" onclick={() => showRevision(job.result_revision_id!)}>결과 보기 ↗</button>{/if}</article>{/each}</div>
          {#if revisions.length}<div class="revision-list"><h3>보존된 revision <small class="muted">최근 100개</small></h3>{#each revisions as revision}<button class="revision-button" onclick={() => showRevision(revision.id)}><span>{revision.id.slice(0, 8)} <span class="muted">· {date(revision.created_at)}</span></span><span class="badge">{project.head_revision_id === revision.id ? 'HEAD' : 'SNAPSHOT'}</span></button>{/each}</div>{/if}
          {#if revisionLoading}<p role="status">결과를 불러오는 중…</p>{/if}
          {#if snapshot}<div class="snapshot"><div class="row"><h3>SongPackage snapshot</h3><span class="badge mock">모의 데이터 · 오디오 없음</span></div><pre>{JSON.stringify(snapshot, null, 2)}</pre></div>{/if}
        </section>
      {:else if !loading}<div class="welcome"><div class="welcome-mark">♫</div><h2>아이디어에 이름을 붙여 보세요.</h2><p class="muted">왼쪽에서 프로젝트를 만들면 작업실이 열립니다.</p></div>{/if}
      <footer>COMPOSER / LOCAL STUDIO <span>Reference → Composition → Sound</span></footer>
    </div>
  </main>
</div>
