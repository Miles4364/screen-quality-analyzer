"""选择文件、后台分析、取消和结果展示。"""
from pathlib import Path
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QComboBox, QInputDialog,
    QSplitter, QStackedWidget, QTreeWidget, QTreeWidgetItem, QScrollArea, QSizePolicy,
)
from gui.analysis_charts import AnalysisCharts
from gui.worker import AnalysisWorker
from storage.analysis_store import AnalysisStore, StorageError
from utils.product import APP_NAME, DISPLAY_VERSION
from utils.time_util import seconds_to_time


class MainWindow(QMainWindow):
    def __init__(self, video_path='', database_path=None):
        super().__init__()
        self.store = AnalysisStore(database_path) if database_path is not None else AnalysisStore()
        self.task_id = None
        self.pending_title = None
        self.pending_project = None
        self.pending_project_name = None
        self.worker = None
        self.result = None
        self.review_dialog = None
        self.report_active = False
        self.reviews = {}
        self._cancel_requested = False
        self._close_pending = False
        self.setWindowTitle(f'{APP_NAME} · {DISPLAY_VERSION}')
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName('title')
        header.addWidget(title)
        header.addStretch()
        self.analysis_nav = QPushButton('分析工作台')
        self.chart_nav = QPushButton('统计图表')
        for button in (self.analysis_nav, self.chart_nav):
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setObjectName('navigation')
            header.addWidget(button)
        self.analysis_nav.setChecked(True)
        outer.addLayout(header)
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(False)
        outer.addWidget(self.workspace_splitter, 1)

        sidebar = QWidget()
        sidebar.setMinimumWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 8, 0)
        side_title = QLabel('项目与任务')
        side_title.setObjectName('sectionTitle')
        side_layout.addWidget(side_title)
        self.sidebar_hint = QLabel('最近 200 个任务 · 双击打开')
        self.sidebar_hint.setObjectName('muted')
        self.sidebar_hint.setWordWrap(True)
        side_layout.addWidget(self.sidebar_hint)
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.project_tree.setAccessibleName('项目与历史任务')
        self.project_tree.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.project_tree.itemActivated.connect(self._activate_tree_item)
        self.project_tree.itemClicked.connect(self._select_tree_project)
        side_layout.addWidget(self.project_tree, 1)
        self.refresh_tree_button = QPushButton('刷新任务列表')
        self.refresh_tree_button.clicked.connect(lambda: self.refresh_projects())
        side_layout.addWidget(self.refresh_tree_button)
        self.workspace_splitter.addWidget(sidebar)

        self.workspace_stack = QStackedWidget()
        workbench = QWidget()
        layout = QVBoxLayout(workbench)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(12)
        subtitle = QLabel('分析工作台')
        subtitle.setObjectName('sectionTitle')
        layout.addWidget(subtitle)
        row = QHBoxLayout()
        self.path_edit = QLineEdit(video_path)
        self.path_edit.setAccessibleName('视频路径')
        self.path_edit.setPlaceholderText('选择视频，或在此粘贴本地文件路径')
        self.browse_button = QPushButton('选择视频')
        self.browse_button.clicked.connect(self.choose_file)
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)
        task_row = QHBoxLayout()
        self.project_picker = QComboBox()
        self.project_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.project_picker.setMinimumContentsLength(6)
        self.project_picker.setMaximumWidth(200)
        self.project_picker.currentTextChanged.connect(self.project_picker.setToolTip)
        self.project_picker.addItem('未分组', None)
        self.new_project_button = QPushButton('新建项目')
        self.new_project_button.clicked.connect(self.create_project)
        self.task_title_edit = QLineEdit()
        self.task_title_edit.setMaxLength(120)
        self.task_title_edit.setPlaceholderText('任务名称（留空使用视频文件名）')
        task_row.addWidget(QLabel('项目'))
        task_row.addWidget(self.project_picker)
        task_row.addWidget(self.new_project_button)
        task_row.addWidget(self.task_title_edit, 1)
        layout.addLayout(task_row)
        self.metadata_label = QLabel('视频参数将在开始分析后显示')
        self.metadata_label.setTextFormat(Qt.TextFormat.PlainText)
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.metadata_label.setObjectName('card')
        layout.addWidget(self.metadata_label)
        controls = QHBoxLayout()
        self.start_button = QPushButton('开始分析')
        self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self.start_analysis)
        self.cancel_button = QPushButton('取消分析')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        controls.addWidget(self.start_button)
        controls.addWidget(self.cancel_button)
        self.history_button = QPushButton('历史记录')
        self.history_button.clicked.connect(self.open_history)
        self.save_result_button = QPushButton('保存结果')
        self.save_result_button.setEnabled(False)
        self.save_result_button.clicked.connect(self.save_result)
        controls.addWidget(self.history_button)
        controls.addWidget(self.save_result_button)
        controls.addStretch()
        self.status_label = QLabel('就绪')
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(24)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.summary_label = QLabel('尚无分析结果')
        self.summary_label.setObjectName('summary')
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        review_controls = QHBoxLayout()
        self.review_filter = QComboBox()
        self.review_filter.addItem('全部复核状态', None)
        from core.review import REVIEW_LABELS
        for key, label in REVIEW_LABELS.items():
            self.review_filter.addItem(label, key)
        self.review_filter.currentIndexChanged.connect(self.apply_review_filter)
        self.edit_review_button = QPushButton('记录人工复核')
        self.edit_review_button.clicked.connect(self.edit_issue_review)
        self.edit_review_button.setEnabled(False)
        self.review_summary = QLabel('')
        self.review_summary.setWordWrap(True)
        review_controls.addWidget(self.review_filter)
        review_controls.addWidget(self.edit_review_button)
        review_controls.addWidget(self.review_summary)
        layout.addLayout(review_controls)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['异常类型', '开始时间', '结束时间', '持续时间', '等级', '说明', '复核状态'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.open_review)
        self.table.itemSelectionChanged.connect(self._update_detail)
        layout.addWidget(self.table, 1)
        self.review_button = QPushButton('查看截图 / 跳转视频')
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.open_review)
        review_row = QHBoxLayout()
        review_row.addWidget(self.review_button)
        self.screenshots_button = QPushButton('已保存截图')
        self.screenshots_button.setEnabled(False)
        self.screenshots_button.clicked.connect(self.open_screenshots)
        review_row.addWidget(self.screenshots_button)
        self.export_button = QPushButton('导出 Excel 报告')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_dialog)
        review_row.addWidget(self.export_button)
        layout.addLayout(review_row)
        hint = QLabel('判定提示：静态 PPT 或低运动画面可能触发疑似冻结，请结合视频人工复核。')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.workspace_stack.addWidget(workbench)
        self.charts = AnalysisCharts()
        self.workspace_stack.addWidget(self.charts)
        self.workspace_splitter.addWidget(self.workspace_stack)
        self.analysis_nav.clicked.connect(lambda: self.workspace_stack.setCurrentIndex(0))
        self.chart_nav.clicked.connect(lambda: self.workspace_stack.setCurrentIndex(1))
        detail_panel = QWidget()
        detail_panel.setMinimumWidth(200)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(10, 0, 0, 0)
        detail_heading = QLabel('任务与事件详情')
        detail_heading.setObjectName('sectionTitle')
        detail_layout.addWidget(detail_heading)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        self.detail_label = QLabel('选择视频开始分析，或从左侧打开历史任务。')
        self.detail_label.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_label.setWordWrap(True)
        self.detail_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail_label.setMargin(14)
        detail_scroll.setWidget(self.detail_label)
        detail_layout.addWidget(detail_scroll, 1)
        self.workspace_splitter.addWidget(detail_panel)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setStretchFactor(2, 0)
        self.workspace_splitter.setSizes([210, 960, 230])
        self.path_edit.textChanged.connect(self._path_changed)
        self.setStyleSheet('''
            QMainWindow { background: #f1f5f3; }
            QWidget { background: #f1f5f3; color: #24483f; font-family: "Microsoft YaHei UI"; font-size: 13px; }
            QLabel#title { font-size: 24px; font-weight: 700; color: #166156; }
            QLabel#sectionTitle { font-size: 17px; font-weight: 600; }
            QLabel#muted { color: #607a71; }
            QLabel#card { background: white; border: 1px solid #c8d9d2; padding: 12px; }
            QLabel#summary { font-size: 14px; font-weight: 600; }
            QLineEdit, QComboBox, QPlainTextEdit { background: white; border: 1px solid #b9cdc4; padding: 8px; }
            QAbstractItemView { background: white; color: #24483f; selection-background-color: #166156; selection-color: white; }
            QScrollArea > QWidget > QLabel { background: white; }
            QToolTip { background: white; color: #24483f; border: 1px solid #b9cdc4; }
            QPushButton { background: white; border: 1px solid #b9cdc4; padding: 9px 14px; }
            QPushButton:hover { background: #e0eee7; border-color: #166156; }
            QPushButton#primary, QPushButton#navigation:checked { background: #166156; color: white; border-color: #166156; }
            QPushButton:disabled { background: #e4ece7; color: #879a92; border-color: #ccd9d2; }
            QProgressBar { border: 1px solid #c8d9d2; background: #e2ece6; text-align: center; height: 18px; }
            QProgressBar::chunk { background: #6ea28e; }
            QTableWidget, QTreeWidget { background: white; alternate-background-color: #f2f7f4; gridline-color: #dfebe4; border: 1px solid #c8d9d2; }
            QTableWidget::item:selected, QTreeWidget::item:selected { background: #166156; color: white; }
            QHeaderView::section { background: #e0ece5; padding: 8px; border: none; font-weight: 600; }
            QScrollArea { background: white; border: 1px solid #c8d9d2; }
            QTabWidget::pane { border: 1px solid #c8d9d2; background: white; }
            QTabBar::tab { background: #e0ece5; border: 1px solid #c8d9d2; padding: 10px 14px; }
            QTabBar::tab:selected { background: #166156; color: white; }
            QSplitter::handle { background: #d8e5de; width: 3px; }
        ''')
        self.refresh_projects()

    def _refresh_task_tree(self, projects):
        self.project_tree.clear()
        groups = {}
        for project in [{'id': None, 'name': '未分组'}, *projects]:
            node = QTreeWidgetItem([project['name']])
            node.setData(0, Qt.ItemDataRole.UserRole, ('project', project['id']))
            self.project_tree.addTopLevelItem(node)
            groups[project['id']] = node
        for task in self.store.list_tasks(limit=200):
            node = QTreeWidgetItem([task['title']])
            node.setData(0, Qt.ItemDataRole.UserRole, ('task', task['id']))
            node.setToolTip(0, f'{task["filename"]}\n{task["issue_count"]} 个异常\n{task["created_at"]}')
            groups.get(task['project_id'], groups[None]).addChild(node)
            if task['id'] == self.task_id:
                self.project_tree.setCurrentItem(node)
        self.project_tree.expandAll()

    def _activate_tree_item(self, item, column=0):
        kind, identifier = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == 'task' and self.worker is None:
            self.load_history(identifier)
            self.analysis_nav.setChecked(True)
            self.workspace_stack.setCurrentIndex(0)

    def _select_tree_project(self, item, column=0):
        kind, identifier = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == 'project' and self.worker is None:
            index = self.project_picker.findData(identifier)
            self.project_picker.setCurrentIndex(max(0, index))

    def _update_detail(self):
        if self.result is None:
            self.detail_label.setText('选择视频开始分析，或从左侧打开历史任务。')
            return
        result = self.result
        metadata = result.video_metadata
        lines = [metadata.filename, '', '分析范围',
                 f'{seconds_to_time(result.analyzed_duration)} · {result.processed_frames} 帧',
                 f'{metadata.resolution} · {metadata.fps:.3f} FPS', '']
        row = self.table.currentRow()
        if 0 <= row < len(result.issues) and not self.table.isRowHidden(row):
            from core.review import REVIEW_LABELS
            issue = result.issues[row]
            record = self.reviews.get(row, {})
            lines += [f'事件 {row + 1} · ' + ('黑屏' if issue.issue_type == 'BLACK_SCREEN' else '疑似冻结'),
                      f'开始：{seconds_to_time(issue.start_time)}',
                      f'结束：{seconds_to_time(issue.end_time)}', f'持续：{issue.duration:.3f} 秒',
                      '', issue.description, '', f'人工复核：{REVIEW_LABELS[record.get("status", "PENDING")]}']
            if record.get('note'):
                lines += ['复核备注', record['note']]
        else:
            lines += ['在结果表中选择一条异常，可查看时间、检测说明与复核备注。']
        if result.warnings:
            lines += ['', '读取提示', *result.warnings]
        self.detail_label.setText('\n'.join(lines))

    @Slot()
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择待分析视频', '',
            '视频文件 (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.ts);;所有文件 (*)',
        )
        if path:
            self.path_edit.setText(path)

    @Slot()
    def _path_changed(self):
        if self.worker is None:
            self.result = None
            self.reviews = {}
            self.edit_review_button.setEnabled(False)
            self.review_summary.clear()
            self.export_button.setEnabled(False)
            self.task_id = None
            self.task_title_edit.clear()
            self.save_result_button.setEnabled(False)
            self.screenshots_button.setEnabled(False)
            self.review_button.setEnabled(False)
            self.table.setRowCount(0)
            self.summary_label.setText('尚无分析结果')
            self.metadata_label.setText('视频参数将在开始分析后显示')
            self.status_label.setText('就绪')
            self.status_label.setToolTip('')
            self.progress_bar.setValue(0)
            self.charts.set_result(None)
            self._update_detail()

    @Slot()
    def start_analysis(self):
        if self.worker is not None:
            return
        path = self.path_edit.text().strip()
        if not Path(path).is_file():
            self.status_label.setText('请选择有效的视频文件')
            return
        self.result = None
        self.charts.set_result(None)
        self._update_detail()
        self.reviews = {}
        self.review_summary.clear()
        self.export_button.setEnabled(False)
        self.task_id = None
        self.save_result_button.setEnabled(False)
        self.screenshots_button.setEnabled(False)
        self.review_button.setEnabled(False)
        self.pending_title = self.task_title_edit.text().strip() or None
        self.pending_project = self.project_picker.currentData()
        self.pending_project_name = self.project_picker.currentText() if self.pending_project else None
        self._cancel_requested = False
        self.table.setRowCount(0)
        self.summary_label.setText('正在分析，完成后显示结果')
        self.metadata_label.setText('正在读取视频参数…')
        self.status_label.setText('正在解析视频…')
        self.status_label.setToolTip('')
        self.progress_bar.setRange(0, 0)
        self._set_busy(True)
        self.worker = AnalysisWorker(path, parent=self)
        self.worker.metadata_ready.connect(self._show_metadata)
        self.worker.progress.connect(self._show_progress)
        self.worker.status.connect(self.status_label.setText)
        self.worker.result_ready.connect(self._show_result)
        self.worker.cancelled.connect(self._show_cancelled)
        self.worker.failed.connect(self._show_error)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _set_busy(self, busy):
        self.project_tree.setEnabled(not busy)
        self.refresh_tree_button.setEnabled(not busy)
        self.edit_review_button.setEnabled(not busy and self.task_id is not None and bool(self.result and self.result.issues))
        self.project_picker.setEnabled(not busy)
        self.new_project_button.setEnabled(not busy)
        self.task_title_edit.setEnabled(not busy)
        self.export_button.setEnabled(not busy and self.result is not None)
        self.save_result_button.setEnabled(not busy and self.result is not None and self.task_id is None)
        self.history_button.setEnabled(not busy)
        self.start_button.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.path_edit.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    @Slot()
    def cancel_analysis(self):
        if self.worker is not None:
            self._cancel_requested = True
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText('正在取消，等待当前操作完成…')

    @Slot(object)
    def _show_metadata(self, metadata):
        self.metadata_label.setText(
            f'{metadata.filename}\n{metadata.resolution}  ·  {metadata.fps:.3f} FPS  ·  '
            f'{seconds_to_time(metadata.duration)}  ·  {metadata.codec}'
        )

    @Slot(int, int)
    def _show_progress(self, processed, total):
        if self._cancel_requested:
            return
        if total > 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(99, int(processed * 100 / total)))
            self.status_label.setText(f'正在分析：{processed} / {total} 帧')
        else:
            self.progress_bar.setRange(0, 0)
            self.status_label.setText(f'正在分析：已读取 {processed} 帧')

    @Slot(object)
    def _show_result(self, result, persist=True):
        # 取消与结果信号可能同时入队；用户发出取消后不展示成功结果。
        if self._cancel_requested:
            self._show_cancelled()
            return
        self.result = result
        self.reviews = {}
        self.table.clearContents()
        self.export_button.setEnabled(self.worker is None)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        stats = result.statistics
        self.summary_label.setText(f'黑屏 {stats["black_count"]} 段    疑似冻结 {stats["freeze_count"]} 段    共 {stats["total_count"]} 个异常')
        q = result.quality
        self.summary_label.setText(self.summary_label.text() + '\n' + (
            f'辅助评分 {q.score:.2f} / 100 · 黑屏扣 {q.black_penalty:.2f} · 疑似冻结扣 {q.freeze_penalty:.2f}'
            if q.score is not None else f'评分不可用：{q.reason}'))
        from core.quality_score import RULE_DESCRIPTION
        self.summary_label.setToolTip(f'{q.rule_version}：{RULE_DESCRIPTION}\n项目自定义指标，需人工复核。历史结果按当前规则计算。')
        if result.warnings:
            self.summary_label.setText(self.summary_label.text() + '\n' + '；'.join(result.warnings))
        self.status_label.setText(f'分析完成 · {result.processed_frames} 帧 · {result.processing_time:.2f} 秒')
        if result.warnings:
            self.status_label.setText('分析完成 · ' + '；'.join(result.warnings))
        self.review_button.setEnabled(bool(result.issues))
        self.table.setRowCount(len(result.issues))
        for row, issue in enumerate(result.issues):
            values = [
                '黑屏' if issue.issue_type == 'BLACK_SCREEN' else '疑似冻结',
                seconds_to_time(issue.start_time), seconds_to_time(issue.end_time),
                f'{issue.duration:.3f} 秒', {'LOW': '低', 'MEDIUM': '中', 'HIGH': '高'}[issue.severity],
                issue.description,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)

        if persist:
            self.save_result()
        self.refresh_reviews()
        self._update_detail()

    def save_result(self):
        if self.result is None or self.task_id is not None:
            return
        try:
            self.task_id = self.store.save_result(self.result, title=self.pending_title, project_id=self.pending_project)
            self.save_result_button.setEnabled(False)
            self.screenshots_button.setEnabled(True)
            self.edit_review_button.setEnabled(self.worker is None and bool(self.result.issues))
            self.status_label.setText(self.status_label.text() + ' · 已保存')
            self.refresh_projects()
        except StorageError as exc:
            self.save_result_button.setEnabled(True)
            self.status_label.setText(f'结果未保存，可点击“保存结果”重试：{exc}')

    def refresh_projects(self, selected='keep'):
        if selected == 'keep':
            selected = self.project_picker.currentData()
        try:
            projects = self.store.list_projects()
            self.project_picker.clear()
            self.project_picker.addItem('未分组', None)
            for project in projects:
                self.project_picker.addItem(project['name'], project['id'])
            index = self.project_picker.findData(selected)
            self.project_picker.setCurrentIndex(max(0, index))
            self._refresh_task_tree(projects)
        except StorageError as exc:
            self.status_label.setText(f'项目列表不可用：{exc}')

    def refresh_reviews(self):
        from core.review import REVIEW_LABELS, review_counts
        self.charts.set_result(self.result, self.reviews.values())
        try:
            records = self.store.load_task(self.task_id)['reviews'] if self.task_id else []
        except StorageError as exc:
            self.status_label.setText(f'复核记录读取失败：{exc}')
            self.edit_review_button.setEnabled(False)
            return
        self.reviews = {r['issue_ordinal']: r for r in records}
        self.charts.set_result(self.result, records)
        for row in range(self.table.rowCount()):
            record = self.reviews.get(row, {})
            item = QTableWidgetItem(REVIEW_LABELS[record.get('status', 'PENDING')])
            item.setToolTip(record.get('note', '') + '\n' + record.get('updated_at', ''))
            self.table.setItem(row, 6, item)
        counts = review_counts(self.table.rowCount(), records)
        self.review_summary.setText(' · '.join(f'{REVIEW_LABELS[k]} {v}' for k,v in counts.items()))
        self.edit_review_button.setEnabled(self.worker is None and self.task_id is not None and bool(self.table.rowCount()))
        self.apply_review_filter()

    def apply_review_filter(self):
        selected = self.review_filter.currentData()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, selected is not None and self.reviews.get(row, {}).get('status', 'PENDING') != selected)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self._update_detail()

    def edit_issue_review(self):
        if self.worker is not None or self.task_id is None:
            return
        row = self.table.currentRow()
        if row < 0 or self.table.isRowHidden(row):
            self.status_label.setText('请先选择一条异常')
            return
        from gui.issue_review_dialog import IssueReviewDialog
        dialog = IssueReviewDialog(self.store, self.task_id, row, self.reviews.get(row, {}), self)
        if dialog.exec():
            self.refresh_reviews()
        dialog.deleteLater()

    def create_project(self):
        name, accepted = QInputDialog.getText(self, '新建项目', '项目名称（最多 80 字符）')
        if accepted:
            try:
                self.refresh_projects(self.store.create_project(name))
            except StorageError as exc:
                self.status_label.setText(str(exc))

    def open_history(self):
        if self.worker is not None:
            return
        from gui.history_dialog import HistoryDialog
        dialog = HistoryDialog(self.store, self)
        if dialog.exec() and dialog.selected_task_id:
            self.load_history(dialog.selected_task_id)
        dialog.deleteLater()
        self.refresh_projects()

    def load_history(self, task_id):
        if self.worker is not None or self.review_dialog is not None:
            return
        try:
            task = self.store.load_task(task_id)
        except StorageError as exc:
            self.status_label.setText(str(exc))
            return
        self.path_edit.setText(task['result'].video_metadata.filepath)
        self.status_label.setToolTip('')
        self._cancel_requested = False
        self.task_id = task_id
        self.refresh_projects(task['project_id'])
        self.task_title_edit.setText(task['title'])
        self._show_metadata(task['result'].video_metadata)
        self._show_result(task['result'], persist=False)
        self.save_result_button.setEnabled(False)
        self.screenshots_button.setEnabled(True)
        available = self.store.source_available(task)
        self.review_button.setEnabled(available and bool(self.result.issues))
        self.status_label.setText('已打开历史结果' if available else '历史结果已打开；源视频缺失或已更改，无法复核。已有截图仍可查看。')

    def export_dialog(self):
        if self.result is None or self.worker is not None:
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出 Excel 报告', '投屏质量分析报告.xlsx', 'Excel 工作簿 (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
                # 补扩展名后若存在目标，让对话框对最终文件名再次确认覆盖。
                if Path(path).exists():
                    from PySide6.QtWidgets import QMessageBox
                    if QMessageBox.question(self, '覆盖报告', f'文件已存在，是否覆盖？\n{path}') != QMessageBox.StandardButton.Yes:
                        return
            self.export_report_to(path, overwrite=True)

    def export_report_to(self, path, overwrite=False):
        if self.result is None or self.worker is not None:
            return
        from copy import deepcopy
        from gui.report_worker import ReportWorker
        try:
            task = self.store.load_task(self.task_id) if self.task_id else None
        except StorageError as exc:
            self.status_label.setText(f'无法读取报告资料：{exc}')
            return
        if task is None:
            task = {'title': self.pending_title or self.result.video_metadata.filename,
                    'project_name': self.pending_project_name}
        self.worker = ReportWorker(deepcopy(self.result), path,
                                   {'task': deepcopy(task), 'overwrite': overwrite,
                                    'protected_paths': [self.store.path]}, self)
        self.report_active = True
        self._cancel_requested = False
        self._set_busy(True)
        self.cancel_button.setText('取消导出')
        self.progress_bar.setRange(0, 0)
        self.status_label.setText('正在生成 Excel 报告…')
        self.worker.ready.connect(self._report_ready)
        self.worker.failed.connect(self._report_failed)
        self.worker.cancelled.connect(self._report_cancelled)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    @Slot(str)
    def _report_ready(self, path):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(f'报告已导出：{Path(path).name}')
        self.status_label.setToolTip(str(path))

    @Slot(str)
    def _report_failed(self, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(f'报告导出失败（分析结果保留）：{message}')

    @Slot()
    def _report_cancelled(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText('报告导出已取消，分析结果保留')

    def open_screenshots(self):
        if self.task_id is None or self.worker is not None:
            return
        from gui.history_dialog import ScreenshotsDialog
        try:
            records = self.store.list_screenshots(self.task_id)
        except StorageError as exc:
            self.status_label.setText(str(exc))
            return
        dialog = ScreenshotsDialog(records, self)
        dialog.exec()
        dialog.deleteLater()

    @Slot()
    def _show_cancelled(self):
        self.result = None
        self.charts.set_result(None)
        self._update_detail()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText('已取消')
        self.summary_label.setText('分析已取消，未生成结果')

    @Slot(str)
    def _show_error(self, message):
        if self._cancel_requested:
            self._show_cancelled()
            return
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText('分析未完成，请查看上方具体原因')
        self.summary_label.setText('未生成结果')
        self.metadata_label.setText(message)

    @Slot()
    def _finished(self):
        worker = self.worker
        self.worker = None
        self.report_active = False
        self.cancel_button.setText('取消分析')
        self._set_busy(False)
        if worker is not None:
            worker.deleteLater()
        if self._close_pending:
            self.close()

    def open_review(self, *args):
        if self.result is None or not self.result.issues or self.worker is not None:
            return
        if self.review_dialog is not None:
            self.review_dialog.raise_()
            return
        if self.task_id is not None:
            try:
                if not self.store.source_available(self.store.load_task(self.task_id)):
                    self.status_label.setText('源视频缺失或已更改，无法复核；已有截图仍可查看。')
                    return
            except StorageError as exc:
                self.status_label.setText(str(exc))
                return
        from gui.review_dialog import ReviewDialog
        row = self.table.currentRow()
        if row < 0 or self.table.isRowHidden(row):
            row = next((r for r in range(self.table.rowCount()) if not self.table.isRowHidden(r)), -1)
        if row < 0:
            self.status_label.setText('当前筛选下没有异常')
            return
        self.table.selectRow(row)
        self.review_dialog = ReviewDialog(self.result, self.result.issues[row], self,
                                          store=self.store if self.task_id else None,
                                          task_id=self.task_id, issue_ordinal=row)
        self.review_dialog.setModal(True)
        self.review_dialog.finished.connect(self._review_finished)
        self.review_dialog.show()

    def _review_finished(self, *args):
        dialog = self.review_dialog
        self.review_dialog = None
        if dialog is not None:
            dialog.deleteLater()
        if self._close_pending:
            self.close()

    def closeEvent(self, event):
        if self.review_dialog is not None:
            self._close_pending = True
            self.review_dialog.close()
            event.ignore()
            return
        if self.worker is not None:
            self._close_pending = True
            self.cancel_analysis()
            event.ignore()
        else:
            event.accept()
