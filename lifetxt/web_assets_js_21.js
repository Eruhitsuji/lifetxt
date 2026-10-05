    // Single-file browser upload. File and receipt metadata live only in memory.
    let attachmentUploadView = null;
    let attachmentUploadPending = false;
    let lastAttachmentUpload = null;

    function disposeAttachmentUpload() {
      if (!attachmentUploadView) return;
      attachmentUploadView.file = null;
      attachmentUploadView.input.value = "";
      attachmentUploadView = null;
    }

    function attachmentText(value) {
      return String(value || "").normalize("NFC").replace(/\p{C}/gu, "").slice(0, 255);
    }

    function attachmentNameValid(name) {
      const value = String(name || "").normalize("NFC");
      return !!value && value === value.trim() && !value.endsWith(".") &&
        !/[\/\\:\p{C}]/u.test(value) && ![".", ".."].includes(value) &&
        !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i.test(value) &&
        new TextEncoder().encode(value).length <= 255;
    }

    function attachmentFeedback(view, message) {
      view.feedback.textContent = t(message);
    }

    function attachmentErrorMessage(error) {
      if (["CLOCK_SKEW", "CLIENT_TIME_REQUIRED"].includes(error?.detail?.error)) return "The browser clock check failed. Check device time and server clock settings, then refresh this record.";
      if (error?.status === 409) return "The source changed. Refresh this record, review it, then select the file again. Nothing is retried automatically.";
      if ([401, 403].includes(error?.status)) return "Upload is not permitted. Check authentication and read-only settings, then refresh this record.";
      if (error?.status === 413) return "The server rejected the file size. Refresh the limit and choose a smaller file.";
      if ([400, 404, 415, 428].includes(error?.status)) return "The server rejected this file or record. Refresh this record and check the filename, file type and item ID.";
      if (error?.status === 429) return "The server is busy. Refresh this record before trying again.";
      return "Upload outcome is uncertain. Refresh this record and inspect its attachments before another attempt; ask the server operator about recovery if needed.";
    }

    function updateAttachmentControls(view) {
      const enabled = view.ready && !view.needsRefresh && !attachmentUploadPending;
      view.input.disabled = !enabled;
      view.submit.disabled = !enabled || !view.file;
      view.refresh.disabled = attachmentUploadPending;
      view.root.setAttribute("aria-busy", String(attachmentUploadPending));
    }

    function renderAttachmentReceipt(view) {
      view.receipt.textContent = "";
      if (lastAttachmentUpload?.itemId !== view.itemId) return;
      const name = document.createElement("p");
      name.className = "attachment-upload-name";
      name.dataset.noI18n = "";
      name.textContent = lastAttachmentUpload.display_name;
      const meta = document.createElement("p");
      meta.dataset.noI18n = "";
      meta.textContent = `${lastAttachmentUpload.media_type} · ${lastAttachmentUpload.size_bytes} ${t("bytes")}`;
      const attached = document.createElement("p");
      attached.textContent = t("Attached (latest upload in this session)");
      view.receipt.append(name, meta, attached);
    }

    async function prepareAttachmentUpload(view) {
      try {
        const policy = await api("/api/attachments/upload", {cache: "no-store"});
        if (attachmentUploadView !== view) return;
        if (policy?.contract_version !== "1" || policy?.upload_enabled !== true ||
            !Number.isSafeInteger(policy.max_upload_bytes) || policy.max_upload_bytes <= 0) {
          attachmentFeedback(view, "Upload is unavailable for this source.");
          return;
        }
        // Bind the visible item to one unchanged authoritative source snapshot.
        // Never use the browser bridge's latest global ETag for this upload.
        const capabilities = await api("/api/capabilities", {cache: "no-store"});
        view.clockHeader = capabilities?.remote_clock?.client_time_header || "X-Lifetxt-Client-Time";
        const before = await api("/api/revision", {cache: "no-store"});
        const data = await api(`/api/items/id/${encodeURIComponent(view.itemId)}`, {cache: "no-store"});
        const after = await api("/api/revision", {cache: "no-store"});
        if (attachmentUploadView !== view) return;
        const item = data?.item;
        const sameRecord = record => JSON.stringify([record?.status, record?.type, record?.title, record?.details]);
        if (!/^[0-9a-f]{64}$/.test(before?.revision || "") || before.revision !== after?.revision ||
            sameRecord(item) !== sameRecord(view.item)) {
          view.needsRefresh = true;
          attachmentFeedback(view, "The source changed. Refresh this record, review it, then select the file again. Nothing is retried automatically.");
          return;
        }
        if (item?.editable !== true || item?.generated || _drawerIdFor(item) !== view.itemId) {
          attachmentFeedback(view, "Upload is unavailable for this source.");
          return;
        }
        view.revision = before.revision;
        view.limit = policy.max_upload_bytes;
        view.ready = true;
        view.limitText.textContent = `${t("Maximum file size")}: ${view.limit} ${t("bytes")}`;
        attachmentFeedback(view, "Choose one file. The server also checks size and file type.");
      } catch (error) {
        if (attachmentUploadView === view) attachmentFeedback(view, [401, 403].includes(error?.status)
          ? attachmentErrorMessage(error) : "Could not check upload availability. Refresh record to try again.");
      } finally {
        if (attachmentUploadView === view) updateAttachmentControls(view);
      }
    }

    function selectAttachmentFile(view) {
      view.file = null;
      const file = view.input.files?.[0];
      view.selected.textContent = file ? `${attachmentText(file.name)} · ${file.size} ${t("bytes")}` : "";
      if (!view.ready || view.needsRefresh || attachmentUploadPending) {
        view.input.value = "";
      } else if (file) {
        if (!attachmentNameValid(file.name)) {
          view.input.value = "";
          attachmentFeedback(view, "Choose a filename without paths, control characters or reserved names.");
        } else if (!Number.isSafeInteger(file.size) || file.size <= 0 || file.size > view.limit) {
          view.input.value = "";
          attachmentFeedback(view, "Choose a non-empty file within the displayed size limit.");
        } else {
          view.file = file;
          attachmentFeedback(view, "Ready to upload. This attaches the file without saving editor changes.");
        }
      }
      updateAttachmentControls(view);
    }

    async function submitAttachmentUpload(view) {
      if (attachmentUploadView !== view || !view.ready || view.needsRefresh || !view.file || attachmentUploadPending) return;
      let file = view.file;
      attachmentUploadPending = true;
      updateAttachmentControls(view);
      attachmentFeedback(view, "Uploading… Keep this page open. Do not submit the file again.");
      try {
        const headers = {
          "Content-Type": "application/octet-stream",
          "X-Lifetxt-Upload": "1",
          "X-Lifetxt-Item-Id": view.itemId,
          "X-Lifetxt-Filename": encodeURIComponent(file.name.normalize("NFC")),
          "X-Lifetxt-Expected-Revision": view.revision,
        };
        if (/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(view.clockHeader) &&
            !Object.keys(headers).some(key => key.toLowerCase() === view.clockHeader.toLowerCase())) {
          headers[view.clockHeader] = new Date().toISOString();
        }
        const result = await api("/api/attachments/upload", {
          method: "POST", cache: "no-store",
          headers,
          body: file,
        });
        // Consume only receipt metadata. The opaque receipt ID grants no access.
        if (result?.contract_version !== "1" || typeof result.display_name !== "string" ||
            typeof result.media_type !== "string" || !Number.isSafeInteger(result.size_bytes) ||
            result.size_bytes !== file.size || !/^[0-9a-f]{64}$/.test(result.source_revision || "")) {
          throw new Error("Invalid upload receipt");
        }
        lastAttachmentUpload = {
          itemId: view.itemId,
          display_name: attachmentText(result.display_name),
          media_type: attachmentText(result.media_type),
          size_bytes: result.size_bytes,
        };
        view.file = null;
        view.input.value = "";
        view.selected.textContent = "";
        view.needsRefresh = true;
        renderAttachmentReceipt(view);
        attachmentFeedback(view, "Attached. Refreshing this record…");
        try {
          await refreshAll();
          const data = await api(`/api/items/id/${encodeURIComponent(view.itemId)}`, {cache: "no-store"});
          if (attachmentUploadView === view && !drawerEditing) openDrawer(data.item, "none");
        } catch (_) {
          if (attachmentUploadView === view) attachmentFeedback(view, "Attached, but the record could not be refreshed. Use Refresh record before another upload.");
        }
      } catch (error) {
        view.needsRefresh = true;
        view.file = null;
        view.input.value = "";
        if (attachmentUploadView === view) attachmentFeedback(view, attachmentErrorMessage(error));
      } finally {
        file = null;
        attachmentUploadPending = false;
        if (attachmentUploadView) updateAttachmentControls(attachmentUploadView);
      }
    }

    function mountAttachmentUpload(item, container) {
      if (!container) return;
      const root = document.createElement("section");
      root.className = "attachment-upload";
      root.setAttribute("aria-label", t("Attachments"));
      const heading = document.createElement("h4");
      heading.textContent = t("Attachments");
      root.append(heading);
      // Do not expose legacy paths as attachment labels or links.
      if ((item.details?.file?.length || 0) + (item.details?.dir?.length || 0)) {
        const summary = document.createElement("p");
        summary.textContent = t("This record has attachment references. Raw record details remain available separately.");
        root.append(summary);
      }
      container.append(root);
      const itemId = _drawerIdFor(item);
      if (!item.editable || item.generated || !itemId || isDisplayMode()) {
        const note = document.createElement("p");
        note.textContent = t("Upload requires an existing writable record with an item ID.");
        root.append(note);
        return;
      }
      const label = document.createElement("label");
      label.textContent = t("Choose attachment");
      label.htmlFor = "attachment-upload-file";
      const input = document.createElement("input");
      input.id = "attachment-upload-file";
      input.type = "file";
      input.disabled = true;
      const limitText = document.createElement("p");
      const selected = document.createElement("p");
      selected.className = "attachment-upload-name";
      selected.dataset.noI18n = "";
      const feedback = document.createElement("p");
      feedback.setAttribute("role", "status");
      feedback.setAttribute("aria-live", "polite");
      feedback.textContent = t("Checking upload availability…");
      const actions = document.createElement("div");
      actions.className = "actions";
      const submit = document.createElement("button");
      submit.id = "attachment-upload-submit";
      submit.type = "button";
      submit.textContent = t("Upload attachment");
      submit.disabled = true;
      const refresh = document.createElement("button");
      refresh.id = "attachment-upload-refresh";
      refresh.type = "button";
      refresh.className = "secondary";
      refresh.textContent = t("Refresh record");
      const receipt = document.createElement("div");
      receipt.id = "attachment-upload-receipt";
      actions.append(submit, refresh);
      root.append(label, input, limitText, selected, actions, feedback, receipt);
      const view = {root, item, itemId, input, limitText, selected, submit, refresh, feedback, receipt,
        ready: false, needsRefresh: false, file: null, revision: null, limit: 0};
      attachmentUploadView = view;
      input.addEventListener("change", () => selectAttachmentFile(view));
      submit.addEventListener("click", () => submitAttachmentUpload(view));
      refresh.addEventListener("click", async () => {
        if (attachmentUploadPending || attachmentUploadView !== view) return;
        view.file = null;
        input.value = "";
        view.ready = false;
        updateAttachmentControls(view);
        try {
          const data = await api(`/api/items/id/${encodeURIComponent(itemId)}`, {cache: "no-store"});
          if (attachmentUploadView === view) openDrawer(data.item, "none");
        } catch (error) {
          if (attachmentUploadView === view) attachmentFeedback(view, attachmentErrorMessage(error));
        }
      });
      renderAttachmentReceipt(view);
      updateAttachmentControls(view);
      prepareAttachmentUpload(view);
    }
