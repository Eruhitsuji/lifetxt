    // Compound work sessions use independent file and timer snapshots.
    let workSessionView = null;
    let workSessionPending = false;
    let drawerWorkEditBinding = null;
    const workHash = value => /^[a-f0-9]{64}$/.test(value || "");
    const workTimerHash = value => value === "<missing>" || workHash(value);
    function workText(en, ja) { return currentLanguage() === "ja" ? ja : en; }
    function workRefreshText() { return workText("Refresh record and review before trying again.", "レコードを再読み込みし、内容を確認してからやり直してください。"); }
    function disposeWorkSession() { workSessionView = null; }
    function workHeaders(binding) {
      const headers = {"Content-Type": "application/json", "If-Match": '"' + binding.itemRevision + '"'};
      if (/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(binding.clockHeader || "") &&
          !["content-type", "if-match"].includes(binding.clockHeader.toLowerCase()))
        headers[binding.clockHeader] = new Date().toISOString();
      return headers;
    }
    function updateWorkControls(view) {
      const available = view.ready && !view.needsRefresh && !workSessionPending;
      view.start.disabled = !available || view.running || ["[x]", "[-]"].includes(view.item.status);
      view.stop.disabled = view.complete.disabled = !available || !view.ownSession;
      view.refresh.disabled = workSessionPending;
      view.root.setAttribute("aria-busy", String(workSessionPending));
      const edit = document.getElementById("drawer-edit-btn");
      if (edit) edit.disabled = !available;
    }
    async function prepareWorkSession(view) {
      try {
        const health = await api("/api/health", {cache:"no-store"});
        if (health.read_only) throw Error("readonly");
        const capability = await api("/api/capabilities", {cache:"no-store"});
        const before = await api("/api/revision", {cache:"no-store"});
        const data = await api(`/api/items/id/${encodeURIComponent(view.id)}`, {cache:"no-store"});
        const session = await api("/api/work-session", {cache:"no-store"});
        const after = await api("/api/revision", {cache:"no-store"});
        if (workSessionView !== view) return;
        const same = item => JSON.stringify([item?.status,item?.type,item?.title,item?.details]);
        if (!workHash(before.revision) || before.revision !== after.revision ||
            same(data.item) !== same(view.item) || data.item?.editable !== true || data.item?.generated ||
            !workTimerHash(session.timer_revision) || typeof session.running !== "boolean") throw Error("snapshot");
        view.itemRevision = before.revision;
        view.timerRevision = session.timer_revision;
        view.clockHeader = capability?.remote_clock?.client_time_header || "X-Lifetxt-Client-Time";
        view.running = session.running;
        view.ownSession = session.running && session.id === view.id &&
          session.item_revision === before.revision && session.file === health.writable_path;
        view.ready = true;
        if (view.ownSession) view.disclosure.open = true;
        view.feedback.textContent = session.running
          ? (view.ownSession ? workText("Work session is running for this task.", "このタスクで作業中です。") : workText("Another work session is running. Open its task to stop it.", "別の作業セッションが実行中です。停止するにはそのタスクを開いてください。"))
          : workText("No work session is running.", "作業セッションは停止中です。");
      } catch (_) {
        if (workSessionView === view) {
          view.needsRefresh = true;
          view.feedback.textContent = workText("Work session is unavailable. ", "作業セッションを利用できません。") + workRefreshText();
        }
      } finally { if (workSessionView === view) updateWorkControls(view); }
    }
    async function submitWorkSession(view, action, done=false) {
      if (workSessionView !== view || !view.ready || view.needsRefresh || workSessionPending) return;
      if ((action === "start" && view.start.disabled) || (action === "stop" && !view.ownSession)) return;
      let refreshedOwn = false;
      workSessionPending = true;
      updateWorkControls(view);
      view.feedback.textContent = workText("Saving work session…", "作業セッションを保存中…");
      try {
        const result = await api("/api/work-session", {method:"POST", headers:workHeaders(view),
          body:JSON.stringify({action, id:view.id, state:"busy", done,
            item_revision:view.itemRevision, timer_revision:view.timerRevision})});
        if (typeof result.running !== "boolean" || result.running !== (action === "start") ||
            !workHash(result.item_revision) || !workTimerHash(result.timer_revision) || !result.transaction_id) throw Error("receipt");
        view.needsRefresh = true;
        view.feedback.textContent = workText("Saved. Refreshing this record…", "保存しました。レコードを再読み込み中…");
        await refreshAll();
        const fresh = await api(`/api/items/id/${encodeURIComponent(view.id)}`, {cache:"no-store"});
        if (workSessionView === view && !drawerEditing) { openDrawer(fresh.item, "none"); refreshedOwn = true; }
      } catch (error) {
        view.needsRefresh = true;
        view.feedback.textContent = (error?.status === 409
          ? workText("The record or timer changed. Nothing is retried automatically. ", "レコードまたはタイマーが更新されています。自動再試行は行いません。")
          : [400,401,403,428].includes(error?.status)
            ? workText("Work session was rejected. ", "作業セッションの更新が拒否されました。")
            : workText("Work session outcome is uncertain. Inspect the record and ask the operator about recovery before another attempt. ", "作業セッションの結果を確認できません。再試行前にレコードを確認し、必要に応じて管理者に復旧を依頼してください。")) + workRefreshText();
      } finally {
        workSessionPending = false;
        if (workSessionView && workSessionView !== view && !refreshedOwn) {
          // A newly mounted view must reacquire after the pending transaction settles.
          workSessionView.ready = false;
          workSessionView.needsRefresh = true;
          workSessionView.feedback.textContent = workRefreshText();
        }
        if (workSessionView) updateWorkControls(workSessionView);
      }
    }
    function mountWorkSession(item, container) {
      const id = _drawerIdFor(item);
      if (!container || item.type !== "T" || item.editable !== true || item.generated || !id) return;
      const root = document.createElement("section");root.className="attachment-upload";
      const title = document.createElement("h4");title.textContent=workText("Work session", "作業セッション");root.append(title);
      const feedback=document.createElement("p");feedback.id="work-session-feedback";feedback.setAttribute("role","status");feedback.setAttribute("aria-live","polite");root.append(feedback);
      if (["[x]", "[-]"].includes(item.status)) {
        const note = document.createElement("p");
        note.textContent = workText("This task is finished; starting work is unavailable.", "完了・取消済みのタスクでは作業を開始できません。");
        root.append(note);
      }
      const disclosure=document.createElement("details");disclosure.className="drawer-disclosure";
      const toggle=document.createElement("summary");toggle.textContent=workText("Work session controls", "作業セッションの操作");disclosure.append(toggle);root.append(disclosure);
      const actions=document.createElement("div");actions.className="actions";disclosure.append(actions);
      const button=(id,en,ja)=>{const b=document.createElement("button");b.type="button";b.className="secondary";b.id=id;b.textContent=workText(en,ja);b.disabled=true;actions.append(b);return b;};
      const start=button("work-session-start","Start work","作業開始"),stop=button("work-session-stop","Stop work","作業停止"),complete=button("work-session-complete","Complete and stop","完了して停止"),refresh=button("work-session-refresh","Refresh record","レコードを再読み込み");
      const view={item,id,root,disclosure,feedback,start,stop,complete,refresh,ready:false,needsRefresh:false};workSessionView=view;container.append(root);
      start.onclick=()=>submitWorkSession(view,"start");stop.onclick=()=>submitWorkSession(view,"stop");complete.onclick=()=>submitWorkSession(view,"stop",true);
      refresh.onclick=async()=>{if(workSessionPending)return;view.ready=false;view.needsRefresh=true;updateWorkControls(view);refresh.disabled=true;try{const data=await api(`/api/items/id/${encodeURIComponent(id)}`,{cache:"no-store"});if(workSessionView===view)openDrawer(data.item,"none");}catch(_){feedback.textContent=workRefreshText();refresh.disabled=false;}};
      feedback.textContent=workText("Checking work session…", "作業セッションを確認中…");refresh.disabled=false;updateWorkControls(view);prepareWorkSession(view);
    }
