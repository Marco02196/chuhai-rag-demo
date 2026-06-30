import argparse
import inspect
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from rag_answer import answer_question, retrieve_context


DEFAULT_DB_PATH = Path(__file__).parent / "output" / "30tian_chuhai.sqlite"


def render_index_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>出海投放 AI 军师</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f7fb;
      color: #182230;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f7fb; color: #182230; }
    button, textarea, select, input { font: inherit; }
    button { cursor: pointer; }
    .shell { min-height: 100vh; }
    .topbar {
      border-bottom: 1px solid #d9e0ea;
      background: rgba(255,255,255,.92);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    .topbar-inner {
      max-width: 1240px;
      margin: 0 auto;
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .mark {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: #fff;
      font-weight: 900;
      background: linear-gradient(135deg, #0f766e, #2563eb);
    }
    h1 { font-size: 20px; line-height: 1.2; margin: 0; letter-spacing: 0; }
    .subline { margin-top: 3px; color: #667085; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .status { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .pill {
      border: 1px solid #d0d9e6;
      background: #fff;
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 13px;
      color: #344054;
    }
    main { max-width: 1240px; margin: 0 auto; padding: 22px 20px 42px; }
    .summary {
      display: grid;
      grid-template-columns: 1.4fr repeat(3, minmax(150px, .5fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .intro, .stat, .workspace-panel {
      background: #fff;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      box-shadow: 0 12px 34px rgba(24,34,48,.06);
    }
    .intro { padding: 16px 18px; }
    .intro strong { display: block; font-size: 17px; margin-bottom: 4px; }
    .intro span { color: #667085; line-height: 1.55; font-size: 14px; }
    .stat { padding: 15px; }
    .stat strong { display: block; font-size: 24px; color: #101828; }
    .stat span { color: #667085; font-size: 13px; }
    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: start;
    }
    .workspace-panel { padding: 18px; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    h2 { font-size: 18px; margin: 0; letter-spacing: 0; }
    .panel-note { color: #667085; font-size: 13px; }
    textarea {
      width: 100%;
      min-height: 156px;
      max-height: 280px;
      resize: vertical;
      padding: 15px;
      border: 1px solid #c9d3e1;
      border-radius: 8px;
      background: #fbfdff;
      color: #182230;
      line-height: 1.6;
      outline: none;
    }
    textarea:focus, select:focus, input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.12); }
    .question-footer {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-top: 8px;
      color: #667085;
      font-size: 12px;
      line-height: 1.5;
    }
    .question-footer strong { color: #344054; }
    .controls {
      display: grid;
      gap: 14px;
      margin-top: 14px;
    }
    .field-label {
      display: block;
      color: #667085;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .04em;
      margin-bottom: 8px;
      text-transform: uppercase;
    }
    .category-cards {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .category-card {
      min-height: 70px;
      padding: 12px;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fff;
      color: #344054;
      text-align: left;
      box-shadow: 0 1px 2px rgba(16,24,40,.04);
    }
    .category-card strong {
      display: block;
      color: #182230;
      font-size: 14px;
      line-height: 1.25;
    }
    .category-card span {
      display: block;
      margin-top: 5px;
      color: #667085;
      font-size: 12px;
      line-height: 1.35;
    }
    .category-card.active {
      border-color: #0f766e;
      background: #effaf6;
      box-shadow: inset 0 0 0 1px #0f766e, 0 6px 16px rgba(15,118,110,.10);
    }
    .ask-options {
      display: grid;
      grid-template-columns: 1fr minmax(180px, .72fr) 170px;
      gap: 10px;
      align-items: end;
    }
    .depth-toggle {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      min-height: 44px;
      padding: 4px;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #f7faff;
    }
    .depth-toggle button {
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #475467;
      font-weight: 800;
    }
    .depth-toggle button.active {
      background: #fff;
      color: #0f766e;
      box-shadow: 0 1px 3px rgba(16,24,40,.10);
    }
    .loading-box {
      display: flex;
      align-items: center;
      gap: 10px;
      color: #344054;
    }
    .spinner {
      width: 18px;
      height: 18px;
      border: 2px solid #c9d3e1;
      border-top-color: #0f766e;
      border-radius: 50%;
      animation: spin .8s linear infinite;
      flex: 0 0 auto;
    }
    .loading-text { font-weight: 800; }
    .loading-dots::after {
      content: "";
      animation: dots 1.2s steps(4, end) infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes dots {
      0% { content: ""; }
      25% { content: "."; }
      50% { content: ".."; }
      75%, 100% { content: "..."; }
    }
    select, input {
      width: 100%;
      min-height: 44px;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid #c9d3e1;
      background: #fff;
      color: #182230;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .primary {
      min-height: 44px;
      border: 0;
      border-radius: 8px;
      background: #0f766e;
      color: #fff;
      font-weight: 800;
      box-shadow: 0 10px 20px rgba(15,118,110,.18);
    }
    .primary:hover { background: #115e59; }
    .primary:disabled { opacity: .62; cursor: not-allowed; box-shadow: none; }
    .hint { margin-top: 10px; color: #667085; font-size: 13px; }
    .result-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    .secondary {
      min-height: 36px;
      padding: 8px 11px;
      border: 1px solid #c9d3e1;
      border-radius: 8px;
      background: #fff;
      color: #344054;
      font-weight: 800;
    }
    .secondary:hover { background: #f7faff; border-color: #b7c6db; }
    .secondary:disabled { opacity: .52; cursor: not-allowed; }
    .feedback {
      display: none;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 10px;
      color: #667085;
      font-size: 13px;
    }
    .feedback.active { display: flex; }
    .feedback button {
      min-height: 32px;
      min-width: 42px;
      border: 1px solid #c9d3e1;
      border-radius: 8px;
      background: #fff;
      color: #344054;
      font-weight: 800;
    }
    .feedback button.active {
      border-color: #0f766e;
      background: #effaf6;
      color: #0f766e;
    }
    .result-shell {
      max-height: 55vh;
      overflow-y: auto;
      margin-top: 14px;
      padding-right: 4px;
      scrollbar-color: #c9d3e1 transparent;
    }
    .result-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; }
    .answer, .sources {
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fbfdff;
      padding: 16px;
      min-height: 58px;
      line-height: 1.75;
    }
    .answer { white-space: pre-wrap; color: #182230; }
    .sources { color: #344054; overflow-wrap: anywhere; }
    .source-card {
      border-top: 1px solid #e4eaf2;
      padding-top: 10px;
      margin-top: 10px;
    }
    .source-card:first-of-type { border-top: 0; margin-top: 8px; padding-top: 0; }
    .source-title { font-weight: 800; color: #182230; }
    .source-path { color: #667085; font-size: 12px; margin-top: 4px; }
    .history {
      margin-top: 16px;
      border-top: 1px solid #e4eaf2;
      padding-top: 14px;
      max-height: 50vh;
      overflow-y: auto;
      padding-right: 4px;
    }
    .history:empty { display: none; }
    .history-title {
      color: #475467;
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 10px;
    }
    .history-card {
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fff;
      padding: 13px;
      margin-top: 10px;
    }
    .history-question {
      color: #182230;
      font-weight: 800;
      line-height: 1.5;
    }
    .history-answer {
      color: #344054;
      line-height: 1.7;
      margin-top: 8px;
      white-space: pre-wrap;
    }
    .history-meta {
      color: #667085;
      font-size: 12px;
      margin-top: 8px;
    }
    .sidebar { display: grid; gap: 12px; }
    .recommend {
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fbfdff;
      padding: 13px;
      margin-bottom: 12px;
    }
    .recommend-title {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      color: #182230;
      font-weight: 900;
      margin-bottom: 9px;
    }
    .recommend-title span {
      color: #667085;
      font-size: 12px;
      font-weight: 700;
    }
    .recommend button {
      display: block;
      width: 100%;
      text-align: left;
      margin: 7px 0 0;
      padding: 10px 11px;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fff;
      color: #182230;
      font-weight: 800;
      line-height: 1.4;
    }
    .recommend button:hover { border-color: #0f766e; background: #effaf6; }
    .sample-group { border-top: 1px solid #e4eaf2; padding-top: 13px; }
    .sample-group:first-of-type { border-top: 0; padding-top: 0; }
    .sample-group h3 { margin: 0 0 8px; color: #475467; font-size: 13px; font-weight: 800; }
    .samples button {
      display: block;
      width: 100%;
      text-align: left;
      margin: 7px 0;
      padding: 11px 12px;
      border: 1px solid #e4eaf2;
      border-radius: 8px;
      background: #f7faff;
      color: #1d2939;
      font-weight: 720;
    }
    .samples button:hover { border-color: #b7c6db; background: #eef6ff; }
    .tag-row { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 10px; }
    .tag { font-size: 12px; color: #475467; background: #eef2f7; border-radius: 999px; padding: 5px 8px; }
    .error { color: #b42318; font-weight: 700; }
    @media (max-width: 980px) {
      .summary, .workspace { grid-template-columns: 1fr; }
      .category-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .ask-options { grid-template-columns: 1fr 1fr; }
      .primary { grid-column: 1 / -1; }
    }
    @media (max-width: 620px) {
      .topbar-inner, main { padding-left: 14px; padding-right: 14px; }
      .topbar-inner { align-items: flex-start; flex-direction: column; }
      .status { justify-content: flex-start; }
      .category-cards, .ask-options { grid-template-columns: 1fr; }
      .workspace-panel, .intro, .stat { padding: 14px; }
      h1 { font-size: 18px; }
    }

    /* OpenDesign handoff polish: product workbench layer */
    :root {
      --canvas: #eef3f7;
      --surface: rgba(255,255,255,.86);
      --surface-strong: #ffffff;
      --ink: #142033;
      --muted: #667085;
      --line: rgba(148,163,184,.32);
      --green: #11836f;
      --blue: #2457d6;
      --amber: #b7791f;
      --danger: #b42318;
      --shadow-soft: 0 18px 48px rgba(28, 42, 62, .08);
      --shadow-lift: 0 20px 50px rgba(17, 131, 111, .14);
      --radius-lg: 20px;
      --radius-md: 14px;
      --ease-out: cubic-bezier(.22, 1, .36, 1);
    }
    body {
      background:
        linear-gradient(180deg, #e8f0f5 0%, #f7f8fb 46%, #eef3f7 100%);
      color: var(--ink);
      -webkit-font-smoothing: antialiased;
    }
    .shell {
      position: relative;
      isolation: isolate;
    }
    .shell::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 260px;
      z-index: -1;
      background:
        linear-gradient(135deg, rgba(13, 84, 77, .96), rgba(31, 77, 164, .88) 52%, rgba(15, 23, 42, .92));
    }
    .topbar {
      border-bottom: 1px solid rgba(255,255,255,.18);
      background: rgba(16, 32, 52, .72);
      color: #fff;
    }
    .topbar-inner { padding-top: 16px; padding-bottom: 16px; }
    .mark {
      width: 42px;
      height: 42px;
      border-radius: 14px;
      background: linear-gradient(135deg, #37c39a, #2d6cdf);
      box-shadow: 0 12px 24px rgba(45,108,223,.24);
    }
    h1 { color: #fff; font-size: 21px; font-weight: 900; }
    .subline { color: rgba(255,255,255,.72); }
    .pill {
      border-color: rgba(255,255,255,.22);
      background: rgba(255,255,255,.12);
      color: rgba(255,255,255,.88);
      backdrop-filter: blur(10px);
    }
    .pill::before {
      content: "";
      display: inline-block;
      width: 6px;
      height: 6px;
      margin-right: 7px;
      border-radius: 99px;
      background: #50d49f;
      vertical-align: 1px;
    }
    main { padding-top: 28px; }
    .summary {
      grid-template-columns: minmax(0, 1.45fr) repeat(3, minmax(140px, .45fr));
      gap: 14px;
      margin-bottom: 14px;
    }
    .intro, .stat, .workspace-panel {
      border-color: rgba(255,255,255,.68);
      border-radius: var(--radius-lg);
      background: var(--surface);
      box-shadow: var(--shadow-soft);
      backdrop-filter: blur(18px);
    }
    .intro {
      position: relative;
      min-height: 176px;
      overflow: hidden;
      padding: 24px;
      color: #fff;
      background:
        linear-gradient(135deg, rgba(20,32,51,.96), rgba(17,95,84,.92) 54%, rgba(36,87,214,.78));
    }
    .intro::after {
      content: "RAG";
      position: absolute;
      right: 24px;
      bottom: -18px;
      color: rgba(255,255,255,.08);
      font-size: 96px;
      line-height: 1;
      font-weight: 1000;
      letter-spacing: 0;
    }
    .intro strong {
      max-width: 560px;
      color: #fff;
      font-size: clamp(26px, 4vw, 44px);
      line-height: 1.05;
      letter-spacing: 0;
      margin-bottom: 14px;
    }
    .intro span {
      position: relative;
      z-index: 1;
      display: block;
      max-width: 650px;
      color: rgba(255,255,255,.78);
      font-size: 15px;
      line-height: 1.75;
    }
    .stat {
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 176px;
      padding: 20px;
    }
    .stat strong { font-size: 30px; letter-spacing: 0; }
    .stat span { line-height: 1.5; }
    .stat::before {
      content: "";
      width: 38px;
      height: 6px;
      border-radius: 99px;
      background: linear-gradient(90deg, var(--green), var(--blue));
    }
    .workflow-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .workflow-step {
      min-height: 76px;
      padding: 14px;
      border: 1px solid rgba(255,255,255,.66);
      border-radius: 16px;
      background: rgba(255,255,255,.74);
      box-shadow: 0 10px 26px rgba(28,42,62,.05);
    }
    .workflow-step small {
      display: block;
      color: var(--green);
      font-size: 12px;
      font-weight: 900;
      margin-bottom: 7px;
    }
    .workflow-step strong {
      display: block;
      color: var(--ink);
      font-size: 14px;
      line-height: 1.35;
    }
    .workspace {
      grid-template-columns: minmax(0, 1fr) 372px;
      gap: 18px;
    }
    .workspace-panel { padding: 20px; }
    .question-panel {
      border-top: 4px solid rgba(17,131,111,.88);
    }
    .panel-head { margin-bottom: 16px; }
    .panel-note {
      padding: 6px 10px;
      border-radius: 999px;
      background: #eef6f3;
      color: #247464;
      font-weight: 800;
    }
    .field-label {
      color: #3b4a5f;
      letter-spacing: 0;
      text-transform: none;
    }
    textarea {
      min-height: 170px;
      border-radius: 16px;
      border-color: rgba(148,163,184,.42);
      background: linear-gradient(180deg, #fff, #f8fbff);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.8);
      transition: border-color .18s var(--ease-out), box-shadow .18s var(--ease-out);
    }
    textarea:focus, select:focus, input:focus {
      border-color: var(--green);
      box-shadow: 0 0 0 4px rgba(17,131,111,.12);
    }
    .question-footer {
      padding: 0 2px;
      font-weight: 700;
    }
    .category-cards { gap: 10px; }
    .category-card {
      position: relative;
      min-height: 88px;
      border-radius: 16px;
      padding: 14px;
      transition: transform .16s var(--ease-out), border-color .16s var(--ease-out), box-shadow .16s var(--ease-out), background-color .16s var(--ease-out);
    }
    .category-card:hover {
      transform: translateY(-1px);
      border-color: rgba(17,131,111,.38);
      box-shadow: 0 12px 24px rgba(28,42,62,.07);
    }
    .category-card strong { font-size: 15px; }
    .category-card span { color: #667085; }
    .category-card.active {
      border-color: rgba(17,131,111,.9);
      background: linear-gradient(180deg, #f0fbf7, #fff);
      box-shadow: inset 0 0 0 1px rgba(17,131,111,.55), var(--shadow-lift);
    }
    .category-card.active::after {
      content: "";
      position: absolute;
      top: 13px;
      right: 13px;
      width: 9px;
      height: 9px;
      border-radius: 99px;
      background: var(--green);
      box-shadow: 0 0 0 4px rgba(17,131,111,.12);
    }
    .ask-options {
      grid-template-columns: 1.05fr minmax(190px, .7fr) 180px;
      padding: 14px;
      border: 1px solid rgba(148,163,184,.26);
      border-radius: 18px;
      background: #f8fbff;
    }
    .depth-toggle {
      border-radius: 14px;
      background: #eef3f8;
      border-color: transparent;
    }
    .depth-toggle button { border-radius: 11px; }
    .depth-toggle button.active {
      color: var(--green);
      box-shadow: 0 8px 18px rgba(28,42,62,.10);
    }
    select, input {
      border-radius: 14px;
      border-color: rgba(148,163,184,.42);
    }
    .primary {
      min-height: 46px;
      border-radius: 14px;
      background: linear-gradient(135deg, #11836f, #2457d6);
      box-shadow: 0 14px 28px rgba(36,87,214,.18);
      transition: transform .16s var(--ease-out), box-shadow .16s var(--ease-out), filter .16s var(--ease-out);
    }
    .primary:hover {
      background: linear-gradient(135deg, #0f766e, #1d4ed8);
      filter: saturate(1.06);
      transform: translateY(-1px);
    }
    .hint {
      padding: 11px 12px;
      border-radius: 14px;
      background: #f8fbff;
      color: #53657d;
      line-height: 1.55;
    }
    .secondary {
      border-radius: 12px;
      background: #fff;
    }
    .result-shell {
      border: 1px solid rgba(148,163,184,.22);
      border-radius: 18px;
      padding: 12px;
      background: #f8fbff;
    }
    .answer, .sources, .history-card {
      border-radius: 15px;
      background: #fff;
    }
    .answer {
      min-height: 86px;
      font-size: 15px;
    }
    .sources {
      background: #fbfcff;
    }
    .loading-box {
      min-height: 62px;
      padding: 12px;
      border-radius: 14px;
      background: #f0fbf7;
      color: #176f61;
    }
    .sidebar {
      position: sticky;
      top: 88px;
      display: grid;
      gap: 14px;
    }
    .samples {
      padding: 18px;
      background: rgba(255,255,255,.80);
    }
    .recommend {
      border-radius: 18px;
      background:
        linear-gradient(180deg, rgba(240,251,247,.96), rgba(255,255,255,.96));
      padding: 14px;
    }
    .recommend button, .samples button {
      border-radius: 14px;
      transition: transform .16s var(--ease-out), border-color .16s var(--ease-out), background-color .16s var(--ease-out);
    }
    .recommend button:hover, .samples button:hover {
      transform: translateX(2px);
    }
    .sample-group {
      padding: 13px;
      border: 1px solid rgba(148,163,184,.22);
      border-radius: 16px;
      background: rgba(255,255,255,.62);
      margin-top: 10px;
    }
    .sample-group:first-of-type { margin-top: 0; }
    .sample-group h3 {
      color: #26384f;
      font-size: 14px;
    }
    .tag {
      background: rgba(36,87,214,.08);
      color: #2457d6;
      font-weight: 800;
    }
    .feedback {
      justify-content: space-between;
      padding: 10px 12px;
      border-radius: 14px;
      background: #fff8eb;
    }
    .feedback button.active {
      border-color: var(--amber);
      background: #fff4db;
      color: #8a5a13;
    }
    @media (max-width: 1100px) {
      .summary { grid-template-columns: 1fr 1fr; }
      .intro { grid-column: 1 / -1; }
      .workflow-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .workspace { grid-template-columns: 1fr; }
      .sidebar { position: static; }
    }
    @media (max-width: 620px) {
      .shell::before { height: 310px; }
      main { padding-top: 18px; }
      .summary, .workflow-strip { grid-template-columns: 1fr; }
      .intro { min-height: auto; }
      .intro strong { font-size: 28px; }
      .stat { min-height: 112px; }
      .ask-options {
        grid-template-columns: 1fr;
        padding: 12px;
      }
      .panel-note { width: 100%; }
      .result-shell { max-height: 62vh; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="mark">AI</div>
          <div>
            <h1>出海投放 AI 军师</h1>
            <div class="subline">30天出海指挥部知识库 · 私有问答助手</div>
          </div>
        </div>
        <div class="status">
          <span class="pill">客户试点版</span>
          <span class="pill">引用来源可追溯</span>
          <span class="pill">访问码保护</span>
        </div>
      </div>
    </header>

    <main>
      <section class="summary">
        <div class="intro">
          <strong>把投放经验变成可追问的策略军师</strong>
          <span>面向出海投放团队的私有知识库问答台。输入真实业务问题，系统会检索 SOP、复盘、素材规则和踩坑经验，输出可执行建议和引用来源。</span>
        </div>
        <div class="stat"><strong>381</strong><span>已入库知识片段</span></div>
        <div class="stat"><strong>5</strong><span>投放业务场景</span></div>
        <div class="stat"><strong>3档</strong><span>快速 / 标准 / 深入回答</span></div>
      </section>

      <section class="workflow-strip" aria-label="诊断流程">
        <div class="workflow-step"><small>01 提问</small><strong>用口语描述真实投放问题</strong></div>
        <div class="workflow-step"><small>02 检索</small><strong>从 SOP、复盘和规则里找证据</strong></div>
        <div class="workflow-step"><small>03 诊断</small><strong>拆原因、给动作、标风险</strong></div>
        <div class="workflow-step"><small>04 复用</small><strong>复制到日报、培训或客户沟通</strong></div>
      </section>

      <section class="workspace">
      <div class="workspace-panel question-panel">
        <div class="panel-head">
          <h2>投放诊断台</h2>
          <span class="panel-note">建议输入真实业务问题</span>
        </div>
        <textarea id="question" placeholder="例如：ROI 下滑但 CTR 没变，是落地页问题还是事件回传问题？"></textarea>
        <div class="question-footer">
          <span id="questionMode">当前：综合诊断</span>
          <span><strong id="charCount">0</strong> 字</span>
        </div>
        <div class="controls">
          <div>
            <label class="field-label">选择诊断方向</label>
            <div class="category-cards" role="listbox" aria-label="问题类型">
              <button type="button" class="category-card active" data-category="">
                <strong>综合诊断</strong><span>不确定原因时先选这个</span>
              </button>
              <button type="button" class="category-card" data-category="ad_strategy">
                <strong>投放决策</strong><span>预算、ROI、人群、放量</span>
              </button>
              <button type="button" class="category-card" data-category="creative_copy">
                <strong>素材文案</strong><span>Hook、脚本、素材疲劳</span>
              </button>
              <button type="button" class="category-card" data-category="tech_execution">
                <strong>数据回传</strong><span>Pixel、CAPI、落地页性能</span>
              </button>
              <button type="button" class="category-card" data-category="risk_playbook">
                <strong>止损风控</strong><span>空烧、封控、自动规则</span>
              </button>
              <button type="button" class="category-card" data-category="review_cases">
                <strong>复盘归因</strong><span>亏损定位和日报复盘</span>
              </button>
            </div>
            <select id="category" class="sr-only" aria-label="问题类型">
              <option value="">全部知识库</option>
              <option value="ad_strategy">投放策略库</option>
              <option value="creative_copy">素材与文案库</option>
              <option value="tech_execution">技术落地库</option>
              <option value="risk_playbook">风控与踩坑库</option>
              <option value="review_cases">复盘案例库</option>
            </select>
          </div>
          <div class="ask-options">
            <div>
              <label class="field-label">回答颗粒度</label>
              <div class="depth-toggle" aria-label="建议深度">
                <button type="button" data-limit="2" data-depth="quick">快速</button>
                <button type="button" class="active" data-limit="3" data-depth="standard">标准</button>
                <button type="button" data-limit="5" data-depth="deep">深入</button>
              </div>
              <input id="limit" class="sr-only" type="number" min="1" max="8" value="3" />
              <input id="depth" class="sr-only" type="text" value="standard" />
            </div>
            <div>
              <label class="field-label" for="accessCode">客户访问码</label>
              <input id="accessCode" type="password" placeholder="输入项目访问码" autocomplete="current-password" />
            </div>
            <button id="ask" class="primary">生成策略建议</button>
          </div>
        </div>
        <div id="formHint" class="hint">请输入演示访问码后生成建议。访问码由项目负责人提供。</div>
        <div class="result-actions">
          <button id="copyAnswer" type="button" class="secondary" disabled>复制回答</button>
          <button id="clearChat" type="button" class="secondary" disabled>清除对话</button>
        </div>
        <div id="feedback" class="feedback">
          <span>这条回答有帮助吗？</span>
          <button type="button" data-feedback="up">有用</button>
          <button type="button" data-feedback="down">没用</button>
        </div>
        <div class="result-shell" aria-live="polite">
          <div class="result-grid">
            <div id="answer" class="answer">等待提问。</div>
            <div id="sources" class="sources"></div>
          </div>
          <div id="history" class="history"></div>
        </div>
      </div>
      <aside class="workspace-panel samples">
        <div class="panel-head">
          <h2>试点问题库</h2>
          <span class="panel-note">点击即填入</span>
        </div>
        <div class="recommend">
          <div class="recommend-title">当前推荐 <span id="recommendMode">综合诊断</span></div>
          <div id="recommendList"></div>
        </div>
        <div class="sample-group">
          <h3>投放策略</h3>
          <button data-q="钱一直烧但是不出单咋办？" data-cat="">烧钱没单怎么办？</button>
          <button data-q="ROI 小于 1 持续两天怎么办？应该关停还是降预算？" data-cat="ad_strategy">ROI 低：关停还是降预算？</button>
          <button data-q="CTR 高但是 CVR 很低，应该优先排查素材、落地页还是人群？" data-cat="ad_strategy">CTR 高但 CVR 低怎么排查？</button>
          <button data-q="TOFU、MOFU、BOFU 分别应该怎么做人群排除？" data-cat="ad_strategy">漏斗人群排除怎么做？</button>
        </div>
        <div class="sample-group">
          <h3>素材文案</h3>
          <button data-q="FB 爆款五步法文案怎么写？" data-cat="creative_copy">FB 爆款文案五步法</button>
          <button data-q="Hook 不够强，怎么改成更高 CTR 的开头？" data-cat="creative_copy">Hook 如何改得更抓人？</button>
          <button data-q="素材疲劳应该看哪些信号？" data-cat="creative_copy">素材疲劳看哪些信号？</button>
        </div>
        <div class="sample-group">
          <h3>技术落地</h3>
          <button data-q="Pixel、CAPI、事件回传应该怎么配置才干净？" data-cat="tech_execution">Pixel/CAPI 回传怎么配置？</button>
          <button data-q="动态参数路由里的 pid、goal、segment 分别承担什么作用？" data-cat="tech_execution">动态参数路由怎么拆？</button>
          <button data-q="LCP、CLS、TBT 超预算时先修哪里？" data-cat="tech_execution">页面性能超预算先修哪里？</button>
        </div>
        <div class="sample-group">
          <h3>风控复盘</h3>
          <button data-q="半夜空烧怎么设置自动拦截规则？" data-cat="risk_playbook">半夜空烧怎么拦截？</button>
          <button data-q="自动化规则怎么避免误杀好计划？" data-cat="risk_playbook">自动规则如何防误杀？</button>
          <button data-q="今天亏损应该归因到素材、受众、落地页还是技术链路？" data-cat="review_cases">亏损复盘怎么归因？</button>
        </div>
        <div class="tag-row">
          <span class="tag">ROI</span>
          <span class="tag">素材疲劳</span>
          <span class="tag">Pixel/CAPI</span>
          <span class="tag">风控熔断</span>
        </div>
      </aside>
    </section>
    </main>
  </div>
  <script>
    const answerEl = document.getElementById("answer");
    const sourcesEl = document.getElementById("sources");
    const askBtn = document.getElementById("ask");
    const questionEl = document.getElementById("question");
    const accessInput = document.getElementById("accessCode");
    const formHint = document.getElementById("formHint");
    const historyEl = document.getElementById("history");
    const copyBtn = document.getElementById("copyAnswer");
    const clearBtn = document.getElementById("clearChat");
    const feedbackEl = document.getElementById("feedback");
    const charCountEl = document.getElementById("charCount");
    const questionModeEl = document.getElementById("questionMode");
    const recommendModeEl = document.getElementById("recommendMode");
    const recommendListEl = document.getElementById("recommendList");
    let latestAnswerText = "";
    let latestQuestionText = "";
    let isLoading = false;
    let loadingTimers = [];
    const categoryLabels = {
      "": "综合诊断",
      "ad_strategy": "投放决策",
      "creative_copy": "素材文案",
      "tech_execution": "数据回传",
      "risk_playbook": "止损风控",
      "review_cases": "复盘归因"
    };
    const recommendedQuestions = {
      "": [
        ["钱一直烧但是不出单咋办？", ""],
        ["ROI 下滑但 CTR 没变，是落地页问题还是事件回传问题？", ""],
        ["今天亏损应该先查素材、人群、落地页还是技术链路？", ""]
      ],
      "ad_strategy": [
        ["ROI 小于 1 持续两天，应该关停还是降预算？", "ad_strategy"],
        ["CTR 高但 CVR 低，投放上先排查什么？", "ad_strategy"],
        ["TOFU、MOFU、BOFU 怎么做人群排除？", "ad_strategy"]
      ],
      "creative_copy": [
        ["Hook 不够强，怎么改成更高 CTR 的开头？", "creative_copy"],
        ["素材疲劳应该看哪些信号？", "creative_copy"],
        ["FB 爆款五步法文案怎么写？", "creative_copy"]
      ],
      "tech_execution": [
        ["Pixel、CAPI、事件回传怎么配置才干净？", "tech_execution"],
        ["动态参数路由里的 pid、goal、segment 分别是什么？", "tech_execution"],
        ["LCP、CLS、TBT 超预算时先修哪里？", "tech_execution"]
      ],
      "risk_playbook": [
        ["半夜空烧怎么设置自动拦截规则？", "risk_playbook"],
        ["自动化规则怎么避免误杀好计划？", "risk_playbook"],
        ["Merchant Score 变差时应该先暂停什么？", "risk_playbook"]
      ],
      "review_cases": [
        ["亏损复盘怎么判断是素材、受众还是落地页问题？", "review_cases"],
        ["投放日报里 CPA 为 0 但 ROAS 正常该怎么解释？", "review_cases"],
        ["怎么把一次失败投放整理成可复用 SOP？", "review_cases"]
      ]
    };
    accessInput.value = sessionStorage.getItem("access_code") || "";
    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]);
    }
    function updateAskState() {
      const hasQuestion = questionEl.value.trim().length > 0;
      const hasCode = accessInput.value.trim().length > 0;
      charCountEl.textContent = questionEl.value.trim().length;
      questionEl.style.height = "auto";
      questionEl.style.height = Math.min(questionEl.scrollHeight, 280) + "px";
      askBtn.disabled = isLoading || !hasQuestion;
      copyBtn.disabled = !latestAnswerText;
      clearBtn.disabled = !latestAnswerText && !historyEl.dataset.ready;
      feedbackEl.classList.toggle("active", Boolean(latestAnswerText));
      if (isLoading) return;
      if (!hasCode) {
        formHint.textContent = "请输入演示访问码后生成建议。访问码由项目负责人提供。";
      } else if (!hasQuestion) {
        formHint.textContent = "先输入一个真实投放问题，再生成策略建议。";
      } else {
        formHint.textContent = "准备就绪，点击生成策略建议。";
      }
    }
    function setLoadingStep(text) {
      answerEl.innerHTML = '<div class="loading-box"><span class="spinner"></span><span class="loading-text">' + escapeHtml(text) + '<span class="loading-dots"></span></span></div>';
      formHint.textContent = text;
    }
    function startLoading() {
      isLoading = true;
      askBtn.disabled = true;
      askBtn.textContent = "正在分析...";
      setLoadingStep("正在检索知识库");
      loadingTimers = [
        setTimeout(() => setLoadingStep("正在生成策略建议"), 1000),
        setTimeout(() => setLoadingStep("正在整理引用来源"), 3500),
      ];
    }
    function stopLoading() {
      loadingTimers.forEach(timer => clearTimeout(timer));
      loadingTimers = [];
      isLoading = false;
      askBtn.textContent = "生成策略建议";
      updateAskState();
    }
    function renderHistoryItem(question, answer, sources) {
      const sourceCount = Array.isArray(sources) ? sources.length : 0;
      if (!historyEl.dataset.ready) {
        historyEl.innerHTML = '<div class="history-title">诊断记录</div>';
        historyEl.dataset.ready = "true";
      }
      historyEl.insertAdjacentHTML("beforeend", (
        '<div class="history-card">' +
        '<div class="history-question">' + escapeHtml(question) + '</div>' +
        '<div class="history-answer">' + escapeHtml(answer) + '</div>' +
        '<div class="history-meta">引用来源 ' + sourceCount + ' 条</div>' +
        '</div>'
      ));
    }
    function recordFeedback(value) {
      if (!latestAnswerText) return;
      const items = JSON.parse(localStorage.getItem("rag_feedback") || "[]");
      items.push({
        value,
        question: latestQuestionText,
        answerPreview: latestAnswerText.slice(0, 240),
        createdAt: new Date().toISOString()
      });
      localStorage.setItem("rag_feedback", JSON.stringify(items.slice(-50)));
      feedbackEl.querySelectorAll("[data-feedback]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.feedback === value);
      });
      formHint.textContent = value === "up" ? "已记录：这条回答有帮助。" : "已记录：这条回答需要改进。";
    }
    accessInput.addEventListener("input", () => {
      sessionStorage.setItem("access_code", accessInput.value.trim());
      updateAskState();
    });
    questionEl.addEventListener("input", updateAskState);
    function setCategory(value) {
      document.getElementById("category").value = value || "";
      document.querySelectorAll("[data-category]").forEach(btn => {
        btn.classList.toggle("active", (btn.dataset.category || "") === (value || ""));
      });
      const label = categoryLabels[value || ""] || "综合诊断";
      questionModeEl.textContent = "当前：" + label;
      recommendModeEl.textContent = label;
      renderRecommendations(value || "");
    }
    function renderRecommendations(categoryKey) {
      const questions = recommendedQuestions[categoryKey] || recommendedQuestions[""];
      recommendListEl.innerHTML = questions.map(([question, cat]) => (
        '<button type="button" data-recommend-q="' + escapeHtml(question) + '" data-recommend-cat="' + escapeHtml(cat) + '">' +
        escapeHtml(question) +
        '</button>'
      )).join("");
      recommendListEl.querySelectorAll("[data-recommend-q]").forEach(btn => {
        btn.addEventListener("click", () => {
          questionEl.value = btn.dataset.recommendQ;
          setCategory(btn.dataset.recommendCat || "");
          updateAskState();
        });
      });
    }
    document.querySelectorAll("[data-category]").forEach(btn => {
      btn.addEventListener("click", () => setCategory(btn.dataset.category || ""));
    });
    document.querySelectorAll("[data-limit]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.getElementById("limit").value = btn.dataset.limit;
        document.getElementById("depth").value = btn.dataset.depth || "standard";
        document.querySelectorAll("[data-limit]").forEach(item => item.classList.toggle("active", item === btn));
      });
    });
    copyBtn.addEventListener("click", async () => {
      if (!latestAnswerText) return;
      try {
        await navigator.clipboard.writeText(latestAnswerText);
        formHint.textContent = "回答已复制，可以粘贴到复盘、群聊或客户沟通里。";
      } catch (err) {
        formHint.textContent = "复制失败，请手动选中回答内容复制。";
      }
    });
    clearBtn.addEventListener("click", () => {
      latestAnswerText = "";
      latestQuestionText = "";
      answerEl.textContent = "等待提问。";
      sourcesEl.textContent = "";
      historyEl.innerHTML = "";
      delete historyEl.dataset.ready;
      feedbackEl.querySelectorAll("[data-feedback]").forEach(btn => btn.classList.remove("active"));
      updateAskState();
    });
    feedbackEl.querySelectorAll("[data-feedback]").forEach(btn => {
      btn.addEventListener("click", () => recordFeedback(btn.dataset.feedback));
    });
    document.querySelectorAll("[data-q]").forEach(btn => {
      btn.addEventListener("click", () => {
        questionEl.value = btn.dataset.q;
        setCategory(btn.dataset.cat || "");
        updateAskState();
      });
    });
    renderRecommendations("");
    updateAskState();
    askBtn.addEventListener("click", async () => {
      const question = questionEl.value.trim();
      if (!question) {
        updateAskState();
        return;
      }
      startLoading();
      sourcesEl.textContent = "";
      try {
        const accessCode = accessInput.value.trim();
        if (!accessCode) {
          throw new Error("请输入演示访问码。");
        }
        sessionStorage.setItem("access_code", accessCode);
        const headers = {"Content-Type": "application/json"};
        if (accessCode) headers["Authorization"] = `Bearer ${accessCode}`;
        const res = await fetch("/api/ask", {
          method: "POST",
          headers,
          body: JSON.stringify({
            question,
            category_key: document.getElementById("category").value || null,
            limit: Number(document.getElementById("limit").value || 3),
            depth: document.getElementById("depth").value || "standard",
            use_llm: true
          })
        });
        const contentType = res.headers.get("content-type") || "";
        const data = contentType.includes("application/json")
          ? await res.json()
          : {error: await res.text()};
        if (!res.ok) {
          const message = res.status === 401
            ? "访问码不正确，请重新输入。"
            : "生成失败，请稍后重试。如持续失败请联系项目负责人。";
          throw new Error(message);
        }
        latestQuestionText = question;
        latestAnswerText = data.answer || "";
        answerEl.textContent = latestAnswerText;
        feedbackEl.querySelectorAll("[data-feedback]").forEach(btn => btn.classList.remove("active"));
        if (Array.isArray(data.sources) && data.sources.length) {
          sourcesEl.innerHTML = "<strong>引用来源</strong>" + data.sources.map(s => (
            '<div class="source-card"><div class="source-title">[' +
            escapeHtml(s.source_number) + "] " + escapeHtml(s.title) +
            '</div><div class="source-path">' + escapeHtml(s.source_path) + '</div></div>'
          )).join("");
        } else {
          sourcesEl.innerHTML = '<strong>引用来源</strong><div class="source-path">暂无命中来源</div>';
        }
        renderHistoryItem(question, latestAnswerText, data.sources || []);
      } catch (err) {
        latestAnswerText = "";
        latestQuestionText = "";
        answerEl.innerHTML = '<span class="error">' + escapeHtml(err.message) + '</span>';
      } finally {
        stopLoading();
      }
    });
  </script>
</body>
</html>
"""


def normalized_headers(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    return {key.lower(): value for key, value in handler.headers.items()}


def check_auth(headers: dict[str, str], expected_api_key: str | None) -> bool:
    expected_api_key = (expected_api_key or "").strip()
    if not expected_api_key:
        return True
    authorization = headers.get("authorization", "").strip()
    if authorization == f"Bearer {expected_api_key}":
        return True
    return headers.get("x-api-key", "").strip() == expected_api_key


def source_payload(context: dict) -> dict:
    metadata = context.get("metadata", {})
    return {
        "source_number": context.get("source_number"),
        "title": metadata.get("title", ""),
        "category": metadata.get("category", ""),
        "category_key": metadata.get("category_key", ""),
        "source_path": metadata.get("source_path", ""),
    }


def check_readiness(db_path: str | Path) -> tuple[dict, int]:
    db_path = Path(db_path)
    if not db_path.exists():
        return {"ok": False, "error": f"database not found: {db_path}"}, 503
    try:
        with sqlite3.connect(db_path) as conn:
            chunk_count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
            fts_count = conn.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    except sqlite3.Error:
        return {"ok": False, "error": "database is not ready"}, 503
    return {"ok": True, "chunks": chunk_count, "chunks_fts": fts_count}, 200


def handle_ask_payload(
    payload: dict,
    db_path: str | Path,
    retriever: Callable[..., list[dict]] = retrieve_context,
    answerer: Callable[..., str] = answer_question,
) -> tuple[dict, int]:
    question = str(payload.get("question") or "").strip()
    if not question:
        return {"error": "question is required"}, 400
    limit = int(payload.get("limit") or 5)
    limit = max(1, min(limit, 8))
    category_key = payload.get("category_key") or None
    use_llm = bool(payload.get("use_llm", True))
    depth = str(payload.get("depth") or "standard")

    contexts = retriever(db_path=Path(db_path), question=question, limit=limit, category_key=category_key)
    signature = inspect.signature(answerer)
    accepts_depth = "depth" in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )
    if accepts_depth:
        answer = answerer(question, contexts, use_llm=use_llm, depth=depth)
    else:
        answer = answerer(question, contexts, use_llm=use_llm)
    response = {
        "answer": answer,
        "sources": [source_payload(context) for context in contexts],
    }
    if bool(payload.get("debug", False)):
        response["contexts"] = contexts
    return response, 200


class RAGRequestHandler(BaseHTTPRequestHandler):
    server_version = "RAGPrototype/0.1"

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json({"ok": True})
            return
        if self.path == "/readyz":
            response, status = check_readiness(getattr(self.server, "db_path"))
            self.send_json(response, status=status)
            return
        if self.path in {"/", "/index.html"}:
            body = render_index_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if self.path != "/api/ask":
            self.send_json({"error": "not found"}, status=404)
            return
        if not check_auth(normalized_headers(self), getattr(self.server, "api_key", "")):
            self.send_json({"error": "unauthorized"}, status=401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            response, status = handle_ask_payload(payload, db_path=getattr(self.server, "db_path"))
            self.send_json(response, status=status)
        except Exception as exc:
            print(f"request_error path={self.path} type={type(exc).__name__}", flush=True)
            self.send_json({"error": "internal server error"}, status=500)

    def log_message(self, format: str, *args) -> None:
        print(
            f"access remote={self.client_address[0]} method={self.command} path={self.path} message={format % args}",
            flush=True,
        )


def run_server(host: str, port: int, db_path: Path, api_key: str = "") -> None:
    readiness, status = check_readiness(db_path)
    if status != 200:
        raise RuntimeError(readiness["error"])
    server = ThreadingHTTPServer((host, port), RAGRequestHandler)
    server.db_path = db_path
    server.api_key = api_key
    print(f"Serving 30天出海指挥部 RAG on http://{host}:{port}")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the 30天出海指挥部 RAG web app.")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)
    parser.add_argument("--db", default=os.environ.get("RAG_DB_PATH", str(DEFAULT_DB_PATH)), type=Path)
    parser.add_argument("--api-key", default=os.environ.get("APP_API_KEY", ""))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_server(args.host, args.port, args.db, api_key=args.api_key)


if __name__ == "__main__":
    main()
