/* @vitest-environment jsdom */

import { describe, expect, it } from "vitest";

import {
  CaptureSession,
  extractEditableText,
  findEditableElement,
  isSupportedEditable,
  shouldIgnoreEditable
} from "../src/captureEngine";

describe("captureEngine editable detection", () => {
  it("supports contenteditable elements", () => {
    const element = document.createElement("div");
    element.setAttribute("contenteditable", "true");
    element.textContent = "작성 중인 브라우저 작업 내용입니다.";

    expect(isSupportedEditable(element)).toBe(true);
    expect(extractEditableText(element)).toBe("작성 중인 브라우저 작업 내용입니다.");
  });

  it("finds editable parent from nested elements", () => {
    const editor = document.createElement("div");
    editor.setAttribute("contenteditable", "true");
    const child = document.createElement("span");
    editor.append(child);
    document.body.append(editor);

    expect(findEditableElement(child)).toBe(editor);
  });

  it("supports role textbox and aria multiline", () => {
    const roleTextbox = document.createElement("div");
    roleTextbox.setAttribute("role", "textbox");
    const ariaTextbox = document.createElement("div");
    ariaTextbox.setAttribute("aria-multiline", "true");

    expect(isSupportedEditable(roleTextbox)).toBe(true);
    expect(isSupportedEditable(ariaTextbox)).toBe(true);
  });

  it("ignores password fields", () => {
    const password = document.createElement("input");
    password.type = "password";

    expect(shouldIgnoreEditable(password)).toBe(true);
  });

  it("does not emit chunks during composition", () => {
    const session = new CaptureSession();
    session.startComposition();

    expect(
      session.update("한글 조합 중간에는 저장하지 않아야 합니다.")
    ).toBeNull();

    session.endComposition();
    const chunk = session.update("한글 조합 중간에는 저장하지 않아야 합니다. 최종 문장입니다.");

    expect(chunk?.text).toContain("한글 조합");
  });

  it("captures short meaningful work notes", () => {
    const session = new CaptureSession();
    const chunk = session.update("버그 수정 완료");

    expect(chunk?.text).toBe("버그 수정 완료");
  });
});
