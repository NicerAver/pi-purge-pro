"use strict";

(function installSuningIarRuntimePatch() {
  if (window.__suningIarRuntime) return;

  const runtime = {
    imageRequests: [],
    drawCalls: [],
    listenerTargets: Object.create(null),
    listenerRegistrations: []
  };
  window.__suningIarRuntime = runtime;

  const nativeAddEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = __iv8__.wrapNative(
    function addEventListener(type, listener, options) {
      const name = String(type);
      const targetName = this === window
        ? "window"
        : this === document
          ? "document"
          : String(this.className || this.id || this.tagName || "other");
      runtime.listenerRegistrations.push([name, targetName]);
      if (name.startsWith("pointer") && !runtime.listenerTargets[name]) {
        runtime.listenerTargets[name] = this;
      }
      return nativeAddEventListener.call(this, type, listener, options);
    },
    "addEventListener"
  );

  function geometry(element) {
    const className = String(element.className || "");
    const id = String(element.id || "");
    const styleLeft = parseFloat(element.style && element.style.left) || 0;
    const styleTop = parseFloat(element.style && element.style.top) || 0;

    if (id.endsWith("_sncaptcha_button") || className.includes("sncaptcha-init-button")) {
      return [0, 0, 312, 40];
    }
    if (className.includes("transparent-icon")) return [styleLeft, 193, 65, 65];
    if (className.includes("slider-panel") || className.includes("slider-wrap")) {
      return [0, 200, 300, 50];
    }
    if (className.includes("image-fragment")) return [styleLeft, styleTop, 64, 64];
    if (className.includes("slide-canvas") || className.includes("image-wrap")) {
      return [0, 0, 300, 180];
    }
    if (className.includes("slide-wrap")) return [0, 0, 300, 250];
    if (className.includes("slide-box")) return [0, 0, 340, 319];
    return null;
  }

  const nativeRect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = __iv8__.wrapNative(
    function getBoundingClientRect() {
      const values = geometry(this);
      if (!values) return nativeRect.call(this);
      const [left, top, width, height] = values;
      return {
        x: left,
        y: top,
        left,
        top,
        width,
        height,
        right: left + width,
        bottom: top + height,
        toJSON() { return this; }
      };
    },
    "getBoundingClientRect"
  );

  for (const [name, index] of [
    ["offsetLeft", 0],
    ["offsetTop", 1],
    ["offsetWidth", 2],
    ["offsetHeight", 3],
    ["clientWidth", 2],
    ["clientHeight", 3]
  ]) {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, name);
    if (!descriptor || !descriptor.configurable) continue;
    Object.defineProperty(HTMLElement.prototype, name, {
      configurable: true,
      enumerable: descriptor.enumerable,
      get() {
        const values = geometry(this);
        return values ? values[index] : descriptor.get.call(this);
      }
    });
  }

  function executeRemoteScript(node, parent, before, nativeInsert) {
    const url = node.src;
    node.removeAttribute("src");
    const result = nativeInsert.call(parent, node, before);
    const response = JSON.parse(__iv8__.data.pyLoadScript(url));
    if (response.status < 200 || response.status >= 300) {
      throw new Error("Suning IAR script HTTP " + response.status);
    }
    (0, eval)(response.body + "\n//# sourceURL=" + url);
    if (typeof node.onload === "function") node.onload.call(node);
    else if (typeof node.onreadystatechange === "function") node.onreadystatechange.call(node);
    return result;
  }

  const nativeAppend = Node.prototype.appendChild;
  const nativeInsertBefore = Node.prototype.insertBefore;
  Node.prototype.appendChild = __iv8__.wrapNative(function appendChild(node) {
    if (node && node.tagName === "SCRIPT" && node.src && /^https?:/.test(node.src)) {
      return executeRemoteScript(node, this, null, nativeAppend);
    }
    return nativeAppend.call(this, node);
  }, "appendChild");
  Node.prototype.insertBefore = __iv8__.wrapNative(function insertBefore(node, before) {
    if (node && node.tagName === "SCRIPT" && node.src && /^https?:/.test(node.src)) {
      return executeRemoteScript(node, this, before, nativeInsertBefore);
    }
    return nativeInsertBefore.call(this, node, before);
  }, "insertBefore");

  const imagePrototype = HTMLImageElement.prototype;
  const srcDescriptor = Object.getOwnPropertyDescriptor(imagePrototype, "src");
  const widthDescriptor = Object.getOwnPropertyDescriptor(imagePrototype, "naturalWidth");
  const heightDescriptor = Object.getOwnPropertyDescriptor(imagePrototype, "naturalHeight");

  function fakeChallengeImageLoad(image, url) {
    image.__suningIarSrc = String(url);
    runtime.imageRequests.push(String(url));
    setTimeout(function dispatchImageLoad() {
      image.dispatchEvent(new Event("load"));
    }, 1);
  }

  Object.defineProperty(imagePrototype, "src", {
    configurable: true,
    enumerable: srcDescriptor.enumerable,
    get() { return this.__suningIarSrc || srcDescriptor.get.call(this); },
    set: __iv8__.wrapNative(function setSrc(url) {
      url = String(url);
      if (url.includes("/iar_prd_jigsaw/")) {
        fakeChallengeImageLoad(this, url);
        return;
      }
      return srcDescriptor.set.call(this, url);
    }, "set src")
  });
  Object.defineProperty(imagePrototype, "naturalWidth", {
    configurable: true,
    get() {
      if (this.__suningIarSrc) return this.__suningIarSrc.includes("_bg_") ? 340 : 64;
      return widthDescriptor.get.call(this);
    }
  });
  Object.defineProperty(imagePrototype, "naturalHeight", {
    configurable: true,
    get() {
      if (this.__suningIarSrc) return this.__suningIarSrc.includes("_bg_") ? 184 : 64;
      return heightDescriptor.get.call(this);
    }
  });

  const nativeSetAttribute = Element.prototype.setAttribute;
  Element.prototype.setAttribute = __iv8__.wrapNative(function setAttribute(name, value) {
    if (this.tagName === "IMG" && String(name).toLowerCase() === "src") {
      const url = String(value);
      if (url.includes("/iar_prd_jigsaw/")) {
        fakeChallengeImageLoad(this, url);
        return;
      }
    }
    return nativeSetAttribute.call(this, name, value);
  }, "setAttribute");

  const canvasPrototype = CanvasRenderingContext2D.prototype;
  const nativeDrawImage = canvasPrototype.drawImage;
  canvasPrototype.drawImage = __iv8__.wrapNative(function drawImage() {
    const args = Array.from(arguments);
    const source = String(args[0] && (args[0].src || args[0].currentSrc || ""));
    if (source.includes("/iar_prd_jigsaw/")) {
      runtime.drawCalls.push({
        src: source,
        args: args.slice(1).map(Number),
        canvas: [this.canvas.width, this.canvas.height]
      });
      return;
    }
    return nativeDrawImage.apply(this, args);
  }, "drawImage");
})();
