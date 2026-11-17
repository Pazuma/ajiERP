const projectFiles = {
	canWrite(frm) {
		return Boolean(frm.perm?.[0]?.write) && !frm.is_new();
	},
	fileName(fileUrl) {
		return decodeURIComponent((fileUrl || "").split("/").pop() || "");
	},
	async save(frm) {
		await frm.save();
		this.render(frm);
	},
	upload(frm) {
		new frappe.ui.FileUploader({
			doctype: frm.doctype,
			docname: frm.docname,
			frm,
			folder: "Home/Attachments",
			allow_multiple: false,
			allow_toggle_private: false,
			make_attachments_public: 0,
			restrictions: { allowed_file_types: [".pdf"] },
			dialog_title: __("添加项目文件"),
			on_success: async (file) => {
				frm.attachments.attachment_uploaded(file);
				const row = frm.add_child("custom_project_files");
				row.file_name = file.file_name || this.fileName(file.file_url);
				row.pdf_file = file.file_url;
				await this.save(frm);
			},
		});
	},
	rename(frm, row) {
		frappe.prompt(
			{
				fieldname: "file_name",
				fieldtype: "Data",
				label: __("文件名称"),
				reqd: 1,
				default: row.file_name,
			},
			async (values) => {
				frappe.model.set_value(row.doctype, row.name, "file_name", values.file_name.trim());
				await this.save(frm);
			},
			__("重命名项目文件"),
			__("保存")
		);
	},
	remove(frm, row) {
		frappe.confirm(__("确定删除项目文件 {0}？", [row.file_name]), async () => {
			frappe.model.clear_doc(row.doctype, row.name);
			frm.refresh_field("custom_project_files");
			frm.dirty();
			await this.save(frm);
		});
	},
	render(frm) {
		const field = frm.fields_dict.custom_project_files_html;
		if (!field) return;

		const canWrite = this.canWrite(frm);
		const rows = frm.doc.custom_project_files || [];
		const $root = $("<div>").addClass("project-files-panel");
		const $toolbar = $("<div>").addClass("project-files-toolbar").appendTo($root);
		if (canWrite) {
			$("<button>")
				.attr("type", "button")
				.addClass("btn btn-primary btn-sm")
				.append(frappe.utils.icon("add", "sm"), document.createTextNode(` ${__("添加文件")}`))
				.on("click", () => this.upload(frm))
				.appendTo($toolbar);
		}

		const $list = $("<div>").addClass("project-files-list").appendTo($root);
		if (!rows.length) {
			$("<div>").addClass("project-files-empty text-muted").text(__("暂无项目文件")).appendTo($list);
		}
		rows.forEach((row) => {
			const $item = $("<div>").addClass("project-file-item").appendTo($list);
			const $main = $("<div>").addClass("project-file-main").appendTo($item);
			$("<span>").addClass("project-file-icon").append(frappe.utils.icon("file", "md")).appendTo($main);
			const $details = $("<div>").addClass("project-file-details").appendTo($main);
			$("<a>")
				.attr({ href: row.pdf_file, target: "_blank", rel: "noopener" })
				.text(row.file_name || this.fileName(row.pdf_file))
				.appendTo($details);
			const uploadedBy = frappe.user_info(row.uploaded_by)?.fullname || row.uploaded_by || __("未知用户");
			const uploadedOn = row.uploaded_on ? frappe.datetime.str_to_user(row.uploaded_on) : "";
			$("<div>").addClass("text-muted small").text([uploadedBy, uploadedOn].filter(Boolean).join(" · ")).appendTo($details);
			if (canWrite) {
				const $actions = $("<div>").addClass("project-file-actions").appendTo($item);
				$("<button>")
					.attr({ type: "button", title: __("重命名"), "aria-label": __("重命名") })
					.addClass("btn btn-default btn-sm btn-icon")
					.append(frappe.utils.icon("edit", "sm"))
					.on("click", () => this.rename(frm, row))
					.appendTo($actions);
				$("<button>")
					.attr({ type: "button", title: __("删除"), "aria-label": __("删除") })
					.addClass("btn btn-default btn-sm btn-icon text-danger")
					.append(frappe.utils.icon("trash", "sm"))
					.on("click", () => this.remove(frm, row))
					.appendTo($actions);
			}
		});
		field.$wrapper.empty().append($root);
	},
};

frappe.ui.form.on("Project", {
	refresh(frm) {
		projectFiles.render(frm);
	},
});
