import threading
import time
from dataclasses import dataclass
import sys

import keyboard
import pyperclip
import win32con
import win32gui
from openai import OpenAI

from ai_stack_common import load_config
from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QFont, QKeySequence, QTextCursor, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


SYSTEM_PROMPT = """You are an assistant that outputs only the final result.

Your output will be pasted directly into the user's current input field.
Therefore, you must output only the final paste-ready content and nothing extra.

Strictly forbidden:
- introductions
- explanations
- comments
- endings
- pleasantries
- titles
- bullet points
- Markdown formatting, unless the user explicitly asks for Markdown
- fenced code blocks
- phrases like "Here is..."
- phrases like "You can..."
- phrases like "Hope this helps"
- any commentary about the answer

Output rules:
- If the user asks for PowerShell, output only directly executable PowerShell content.
- If the user asks for an article, output only the article body.
- If the user asks for a translation, output only the translation.
- If the user asks for a rewrite, output only the rewritten result.
- If the user asks for code, output only the code itself.
- If the user specifies a format, follow that format strictly.
- If the user asks for Chinese output, use Traditional Chinese unless the user explicitly asks for Simplified Chinese.
- Prefer the shortest sufficient answer that fully satisfies the request.
- Do not overthink.
- Minimize internal reasoning and avoid long deliberation.
- When multiple valid answers exist, choose the most direct one quickly.
- If you cannot produce a directly paste-ready answer, output nothing.
- In that case, stop immediately and do not continue reasoning.

If information is incomplete, do not explain limitations, do not ask follow-up questions, and do not add commentary.
Instead, output the shortest, most reasonable, directly usable result."""


@dataclass
class AppConfig:
    base_url: str = "http://localhost:8080/v1"
    api_key: str = "EMPTY"
    model: str = "Qwen3.5-9B"
    hotkey: str = "ctrl+space"


class LlmWorker(QObject):
    answer_chunk = Signal(str)
    thinking_chunk = Signal(str)
    started = Signal()
    finished = Signal(bool)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, client: OpenAI, model: str, prompt: str, enable_thinking: bool):
        super().__init__()
        self._client = client
        self._model = model
        self._prompt = prompt
        self._enable_thinking = enable_thinking
        self._received_reasoning = False
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        self.started.emit()
        stream = None
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._prompt},
                ],
                temperature=0.4,
                top_p=0.9,
                stream=True,
            )
            for part in stream:
                if self._cancel_requested:
                    close_stream = getattr(stream, "close", None)
                    if callable(close_stream):
                        close_stream()
                    self.cancelled.emit()
                    return
                if not part.choices:
                    continue
                delta = part.choices[0].delta
                reasoning = getattr(delta, 'model_extra', {}).get('reasoning_content')
                if self._enable_thinking and reasoning:
                    self._received_reasoning = True
                    self.thinking_chunk.emit(reasoning)
                if delta.content:
                    self.answer_chunk.emit(delta.content)
            self.finished.emit(self._received_reasoning)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class PromptWindow(QMainWindow):
    request_show = Signal()
    request_toggle = Signal()

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.client = OpenAI(base_url=config.base_url, api_key=config.api_key)
        self.worker_thread: QThread | None = None
        self.worker: LlmWorker | None = None
        self.last_foreground_hwnd: int | None = None
        self.is_generating = False

        self.setWindowTitle("Local AI Prompt")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
        )
        self.resize(860, 760)
        self.request_show.connect(self.show_prompt_window)
        self.request_toggle.connect(self.toggle_prompt_window)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("輸入要生成的內容，Enter 送出，Shift+Enter 換行")
        self.prompt_input.setMinimumHeight(140)
        self.prompt_input.installEventFilter(self)

        self.thinking_checkbox = QCheckBox("Thinking")
        self.thinking_checkbox.toggled.connect(self.on_thinking_toggled)

        self.thinking_view = QTextEdit()
        self.thinking_view.setReadOnly(True)
        self.thinking_view.setPlaceholderText("勾選 Thinking 後，會顯示模型回傳的 reasoning_content")
        self.thinking_view.setStyleSheet("color: #9aa0a6;")
        self.thinking_view.setVisible(False)
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setPlaceholderText("模型輸出會顯示在這裡")

        mono = QFont("Consolas")
        mono.setPointSize(11)
        self.prompt_input.setFont(mono)
        self.thinking_view.setFont(mono)
        self.output_view.setFont(mono)

        self.prompt_label = QLabel("Prompt")
        self.thinking_label = QLabel("Thinking")
        self.output_label = QLabel("輸出")
        self.model_label = QLabel(f"模型: {self.config.model}")
        self.status_label = QLabel(f"快捷鍵: {self.config.hotkey}")
        self.thinking_label.setVisible(False)

        self.generate_button = QPushButton("生成 (Enter)")
        self.cancel_button = QPushButton("取消 (Esc)")
        self.paste_button = QPushButton("貼上 (Ctrl+P)")
        self.close_button = QPushButton("隱藏 (Ctrl+Space)")

        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.generate_button.setDefault(True)
        self.generate_button.setAutoDefault(True)
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        self.paste_button.clicked.connect(self.on_paste_clicked)
        self.close_button.clicked.connect(self.hide)
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.paste_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.thinking_checkbox.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setEnabled(False)
        self.paste_button.setEnabled(False)

        self.generate_return_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.generate_return_shortcut.activated.connect(self.on_generate_clicked)
        self.generate_enter_shortcut = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self.generate_enter_shortcut.activated.connect(self.on_generate_clicked)
        self.cancel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.cancel_shortcut.activated.connect(self.on_cancel_clicked)

        button_row = QHBoxLayout()
        button_row.addWidget(self.generate_button)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.paste_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)

        prompt_header_row = QHBoxLayout()
        prompt_header_row.setSpacing(10)
        prompt_header_row.addWidget(self.prompt_label)
        prompt_header_row.addStretch()
        prompt_header_row.addWidget(self.model_label)

        thinking_header_row = QHBoxLayout()
        thinking_header_row.addWidget(self.thinking_label)
        thinking_header_row.addStretch()
        thinking_header_row.addWidget(self.thinking_checkbox)

        output_header_row = QHBoxLayout()
        output_header_row.addWidget(self.output_label)
        output_header_row.addStretch()

        footer_row = QHBoxLayout()
        footer_row.addWidget(self.status_label)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addLayout(prompt_header_row)
        layout.addWidget(self.prompt_input)
        layout.addLayout(thinking_header_row)
        layout.addWidget(self.thinking_view)
        layout.addLayout(output_header_row)
        layout.addWidget(self.output_view)
        layout.addLayout(footer_row)
        layout.addLayout(button_row)

        container = QWidget()
        container.setObjectName("root")
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.apply_styles()
        self.set_status(f"待命中，按 {self.config.hotkey} 開啟小視窗")

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#root {
                background: #f4f1ea;
            }
            QLabel {
                color: #3a342d;
            }
            QLabel[role="section"] {
                font-size: 15px;
                font-weight: 700;
                color: #2f2923;
            }
            QLabel[role="muted"] {
                color: #766b60;
                font-size: 12px;
            }
            QLabel[role="badge"] {
                background: #e7dfd1;
                color: #43372d;
                border: 1px solid #d2c5af;
                border-radius: 12px;
                padding: 6px 10px;
                font-weight: 700;
            }
            QLabel[role="status"] {
                border-radius: 12px;
                padding: 7px 12px;
                font-weight: 700;
            }
            QLabel[state="idle"] {
                background: #e8e0d3;
                color: #4a4035;
            }
            QLabel[state="working"] {
                background: #d9e8d8;
                color: #234b27;
            }
            QLabel[state="done"] {
                background: #d8ebe4;
                color: #12473a;
            }
            QLabel[state="warning"] {
                background: #f2e1c5;
                color: #7a4d13;
            }
            QLabel[state="error"] {
                background: #f1d5d0;
                color: #7a221d;
            }
            QTextEdit {
                background: #fffdf8;
                border: 1px solid #d8cdbd;
                border-radius: 14px;
                padding: 10px 12px;
                selection-background-color: #c6d8f2;
            }
            QTextEdit:focus {
                border: 1px solid #6e97c8;
            }
            QPushButton {
                background: #efe4d2;
                color: #342b23;
                border: 1px solid #d6c4ab;
                border-radius: 12px;
                padding: 9px 14px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background: #e7dac4;
            }
            QPushButton:disabled {
                background: #e2dbcf;
                color: #9b9082;
                border: 1px solid #d1c6b6;
                padding: 9px 14px;
            }
            QPushButton[role="primary"] {
                background: #2b5f56;
                color: #f7f4ee;
                border: 1px solid #244e47;
            }
            QPushButton[role="primary"]:hover {
                background: #234f48;
            }
            QPushButton[role="danger"] {
                background: #efe0d8;
                color: #7a2b21;
                border: 1px solid #d4b2a8;
            }
            QPushButton[role="danger"]:hover {
                background: #e8d4ca;
            }
            QPushButton[role="primary"]:disabled,
            QPushButton[role="danger"]:disabled {
                background: #ddd6cb;
                color: #9d9387;
                border: 1px solid #cbc1b3;
            }
            QCheckBox {
                color: #54493d;
                spacing: 8px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #bba990;
                border-radius: 4px;
                background: #fffdf8;
            }
            QCheckBox::indicator:checked {
                background: #dfe9e3;
                border: 1px solid #9fb7a8;
            }
            """
        )
        self.prompt_label.setProperty("role", "section")
        self.thinking_label.setProperty("role", "section")
        self.output_label.setProperty("role", "section")
        self.model_label.setProperty("role", "badge")
        self.status_label.setProperty("role", "status")
        self.generate_button.setProperty("role", "primary")
        self.cancel_button.setProperty("role", "danger")
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        widgets = (
            self.prompt_label,
            self.thinking_label,
            self.output_label,
            self.model_label,
            self.status_label,
            self.generate_button,
            self.cancel_button,
        )
        for widget in widgets:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def set_status(self, text: str, state: str = "idle") -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self._refresh_styles()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.prompt_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_P and event.modifiers() & Qt.ControlModifier:
                self.on_paste_clicked()
                return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self.on_generate_clicked()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_P and event.modifiers() & Qt.ControlModifier:
            self.on_paste_clicked()
            return
        super().keyPressEvent(event)

    @Slot(bool)
    def on_thinking_toggled(self, checked: bool) -> None:
        self.thinking_label.setVisible(checked)
        self.thinking_view.setVisible(checked)
        if not checked:
            self.thinking_view.clear()

    @Slot()
    def show_prompt_window(self) -> None:
        foreground_hwnd = win32gui.GetForegroundWindow()
        own_hwnd = int(self.winId()) if self.winId() else None
        if foreground_hwnd and foreground_hwnd != own_hwnd:
            self.last_foreground_hwnd = foreground_hwnd
        self.show()
        self.focus_prompt_window()
        QTimer.singleShot(0, self.focus_prompt_input)

    @Slot()
    def focus_prompt_window(self) -> None:
        self.raise_()
        self.activateWindow()
        hwnd = int(self.winId()) if self.winId() else None
        if not hwnd:
            return
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

    @Slot()
    def focus_prompt_input(self) -> None:
        self.focus_prompt_window()
        self.prompt_input.setFocus(Qt.OtherFocusReason)
        self.prompt_input.selectAll()

    @Slot()
    def toggle_prompt_window(self) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show_prompt_window()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.ignore()
        self.hide()

    def on_generate_clicked(self) -> None:
        if self.is_generating:
            self.set_status("生成中，請等待目前請求完成", "warning")
            return

        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            self.set_status("請先輸入 prompt", "warning")
            self.prompt_input.setFocus()
            return

        self.output_view.clear()
        self.thinking_view.clear()
        self.paste_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.thinking_checkbox.setEnabled(False)
        self.set_status("生成中...", "working")
        self.is_generating = True

        self.worker_thread = QThread()
        self.worker = LlmWorker(
            self.client,
            self.config.model,
            prompt,
            self.thinking_checkbox.isChecked(),
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.answer_chunk.connect(self.append_output)
        self.worker.thinking_chunk.connect(self.append_thinking)
        self.worker.started.connect(self.on_generation_started)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.cancelled.connect(self.on_generation_cancelled)
        self.worker.failed.connect(self.on_generation_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.cancelled.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()

    @Slot()
    def on_cancel_clicked(self) -> None:
        if not self.is_generating or self.worker is None:
            return
        self.cancel_button.setEnabled(False)
        self.set_status("取消中...", "warning")
        self.worker.cancel()

    @Slot()
    def on_generation_started(self) -> None:
        if self.thinking_checkbox.isChecked():
            self.set_status("模型正在輸出 Thinking 與答案...", "working")
        else:
            self.set_status("模型正在輸出...", "working")

    @Slot(str)
    def append_output(self, text: str) -> None:
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output_view.setTextCursor(cursor)
        self.output_view.ensureCursorVisible()

    @Slot(str)
    def append_thinking(self, text: str) -> None:
        cursor = self.thinking_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.thinking_view.setTextCursor(cursor)
        self.thinking_view.ensureCursorVisible()

    @Slot(bool)
    def on_generation_finished(self, received_reasoning: bool) -> None:
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.thinking_checkbox.setEnabled(True)
        if self.thinking_checkbox.isChecked() and not received_reasoning:
            self.thinking_view.setPlainText("This model did not return reasoning_content.")
        has_output = bool(self.output_view.toPlainText().strip())
        self.paste_button.setEnabled(has_output)
        self.set_status("生成完成，可直接貼上", "done")

    @Slot()
    def on_generation_cancelled(self) -> None:
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.thinking_checkbox.setEnabled(True)
        has_output = bool(self.output_view.toPlainText().strip())
        self.paste_button.setEnabled(has_output)
        self.set_status("已取消，保留目前已生成內容", "warning")

    @Slot(str)
    def on_generation_failed(self, message: str) -> None:
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.thinking_checkbox.setEnabled(True)
        self.paste_button.setEnabled(False)
        self.set_status("生成失敗", "error")
        QMessageBox.critical(self, "模型呼叫失敗", message)

    @Slot()
    def cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    def on_paste_clicked(self) -> None:
        content = self.output_view.toPlainText()
        if not content.strip():
            self.set_status("目前沒有可貼上的內容", "warning")
            return

        pyperclip.copy(content)
        target_hwnd = self.last_foreground_hwnd
        self.hide()
        self.set_status("已複製到剪貼簿，準備貼回原視窗", "done")

        if not target_hwnd or not win32gui.IsWindow(target_hwnd):
            return

        def restore_and_paste() -> None:
            try:
                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
                time.sleep(0.12)
                keyboard.press_and_release("ctrl+v")
            except Exception:
                pass

        threading.Thread(target=restore_and_paste, daemon=True).start()


def register_hotkey(window: PromptWindow, hotkey: str) -> None:
    def callback() -> None:
        window.request_toggle.emit()

    keyboard.add_hotkey(hotkey, callback, suppress=False)


def main(config: AppConfig | None = None, show_on_start: bool = True) -> int:
    app = QApplication(sys.argv)
    if config is None:
        config_data = load_config()
        config = AppConfig(
            model=config_data.get("model", AppConfig.model),
        )
    window = PromptWindow(config)
    register_hotkey(window, config.hotkey)
    if show_on_start:
        window.show_prompt_window()

    app.aboutToQuit.connect(keyboard.unhook_all_hotkeys)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
