import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { 
  getTags, 
  createTag, 
  updateTag, 
  deleteTag,
  getUser
} from "../../modules/apiCalls";
import { TTag } from "../../types";
import { TUserData } from "../../types/chatTypes";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ActionIcon } from "@mantine/core";
import { IconMenu2 } from "@tabler/icons-react";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";

export default function TagsPage() {
  const { chatState, startup, toggleSidebar, setUser } = useStore((state) => ({
    chatState: state.chatState,
    startup: state.startup,
    toggleSidebar: state.toggleSidebar,
    setUser: state.setUser,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const canManageTags = useIsFeatureEnabled("tags-management");
  const [tags, setTags] = useState<TTag[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingTag, setEditingTag] = useState<TTag | null>(null);
  const [hoveredHeaderButton, setHoveredHeaderButton] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    color: "#4a9eff",
    enabled: true,
  });

  useEffect(() => {
    const loadUser = async () => {
      try {
        const user = (await getUser()) as TUserData;
        setUser(user);
      } catch (error) {
        console.error("Error loading user:", error);
      }
    };
    
    loadUser();
    startup();
  }, [startup, setUser]);

  useEffect(() => {
    if (canManageTags === true) {
      loadTags();
    }
  }, [canManageTags]);

  const loadTags = async () => {
    try {
      setIsLoading(true);
      const data = await getTags();
      setTags(data);
    } catch (error) {
      console.error("Error loading tags:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingTag(null);
    setFormData({
      title: "",
      description: "",
      color: "#4a9eff",
      enabled: true,
    });
    setShowForm(true);
  };

  const handleEdit = (tag: TTag) => {
    setEditingTag(tag);
    setFormData({
      title: tag.title,
      description: tag.description || "",
      color: tag.color || "#4a9eff",
      enabled: tag.enabled,
    });
    setShowForm(true);
  };

  const handleDelete = async (tagId: number) => {
    if (!window.confirm(t("confirm-delete-tag") || "Are you sure you want to delete this tag?")) {
      return;
    }
    try {
      await deleteTag(tagId);
      loadTags();
    } catch (error) {
      console.error("Error deleting tag:", error);
      alert(t("error-deleting-tag") || "Error deleting tag");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingTag) {
        await updateTag(editingTag.id, formData);
      } else {
        await createTag(formData);
      }
      setShowForm(false);
      setEditingTag(null);
      loadTags();
    } catch (error: any) {
      console.error("Error saving tag:", error);
      alert(error.response?.data?.message || t("error-saving-tag") || "Error saving tag");
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingTag(null);
    setFormData({
      title: "",
      description: "",
      color: "#4a9eff",
      enabled: true,
    });
  };

  if (canManageTags === false) {
    return null;
  }

  return (
      <main className="d-flex pos-relative h-viewport">
        {chatState.isSidebarOpened && <Sidebar />}
        <div className="dashboard-container relative">
          {!chatState.isSidebarOpened && (
            <div className="absolute top-6 left-6 z-10">
              <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
                <IconMenu2 size={20} />
              </ActionIcon>
            </div>
          )}
          <div className="max-w-7xl mx-auto px-4">
            <div className="dashboard-header mb-8">
              <div className="flex items-center gap-4 mb-4">
                {!chatState.isSidebarOpened && (
                  <div className="w-10"></div>
                )}
                <button 
                  className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                    hoveredHeaderButton === 'back' 
                      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                  }`}
                  style={{ transform: 'none' }}
                  onMouseEnter={() => setHoveredHeaderButton('back')}
                  onMouseLeave={() => setHoveredHeaderButton(null)}
                  onClick={() => {
                    setHoveredHeaderButton('back');
                    setTimeout(() => {
                      navigate("/dashboard");
                      setHoveredHeaderButton(null);
                    }, 200);
                  }}
                >
                  ← {t("back-to-dashboard")}
                </button>
              </div>
              <h1 className="text-4xl font-bold mb-8 text-center text-white tracking-tight" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
                {t("tags") || "Tags"}
              </h1>
            </div>

            <div className="mb-12 text-center">
              <button 
                className={`px-4 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                  hoveredHeaderButton === 'create' 
                    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
                }`}
                style={{ transform: 'none' }}
                onMouseEnter={() => setHoveredHeaderButton('create')}
                onMouseLeave={() => setHoveredHeaderButton(null)}
                onClick={() => {
                  setHoveredHeaderButton('create');
                  setTimeout(() => {
                    handleCreate();
                    setHoveredHeaderButton(null);
                  }, 200);
                }}
              >
                {t("create-tag") || "+ New Tag"}
              </button>
            </div>

            {isLoading ? (
              <div className="text-center py-10 text-lg text-[rgb(156,156,156)]">
                {t("loading")}...
              </div>
            ) : tags.length === 0 ? (
              <div className="text-center py-16 text-xl text-[rgb(156,156,156)]">
                {t("no-tags-found") || "No tags found. Create your first one!"}
              </div>
            ) : (
              <div className="flex justify-center w-full">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-fit">
                  {tags.map((tag) => (
                    <TagCard
                      key={tag.id}
                      tag={tag}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      t={t}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {showForm && (
            <TagForm
              formData={formData}
              setFormData={setFormData}
              onSubmit={handleSubmit}
              onCancel={handleCancel}
              editingTag={editingTag}
              t={t}
            />
          )}
        </div>
      </main>
  );
}

interface TagCardProps {
  tag: TTag;
  onEdit: (tag: TTag) => void;
  onDelete: (tagId: number) => void;
  t: any;
}

function TagCard({ tag, onEdit, onDelete, t }: TagCardProps) {
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  
  return (
    <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-6 flex flex-col gap-4 shadow-lg">
      <div className="flex justify-between items-start">
        <h3 className="text-xl font-bold text-white ml-2">{tag.title}</h3>
        <span className={`px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap ${
          tag.enabled 
            ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
            : 'bg-red-500/20 text-red-400 border border-red-500/30'
        }`}>
          {tag.enabled ? t("enabled") || "Enabled" : t("disabled") || "Disabled"}
        </span>
      </div>
      
      {tag.description && (
        <p className="text-sm leading-relaxed text-[rgb(156,156,156)]">
          {tag.description}
        </p>
      )}
      
      <div className="flex gap-3 mt-2 pt-4 border-t border-[rgba(255,255,255,0.1)]">
        <button 
          className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
            hoveredButton === 'edit' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('edit')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={() => {
            setHoveredButton('edit');
            setTimeout(() => {
              onEdit(tag);
              setHoveredButton(null);
            }, 200);
          }}
        >
          {t("edit") || "Edit"}
        </button>
        <button 
          className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
            hoveredButton === 'delete' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('delete')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={() => {
            setHoveredButton('delete');
            setTimeout(() => {
              onDelete(tag.id);
              setHoveredButton(null);
            }, 200);
          }}
        >
          {t("delete") || "Delete"}
        </button>
      </div>
    </div>
  );
}

interface TagFormProps {
  formData: {
    title: string;
    description: string;
    color: string;
    enabled: boolean;
  };
  setFormData: React.Dispatch<React.SetStateAction<any>>;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
  editingTag: TTag | null;
  t: any;
}

function TagForm({ formData, setFormData, onSubmit, onCancel, editingTag, t }: TagFormProps) {
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  
  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-lg">
        <h2 className="!text-xl font-bold text-white text-center mb-6" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
          {editingTag ? t("edit-tag") || "Edit Tag" : t("create-tag") || "Create Tag"}
        </h2>
        <form onSubmit={onSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-[rgb(156,156,156)]">{t("title") || "Title"}</label>
            <input
              type="text"
              maxLength={50}
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
              placeholder={t("tag-title-placeholder") || "Tag title (max 50 characters)"}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-[rgb(156,156,156)]">{t("description") || "Description"}</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={4}
              className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)] resize-none"
              placeholder={t("tag-description-placeholder") || "Tag description (optional)"}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-[rgb(156,156,156)]">{t("color") || "Color"}</label>
            <div className="flex gap-3 items-center">
              <input
                type="color"
                value={formData.color}
                onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                className="w-16 h-12 rounded cursor-pointer border border-[rgba(255,255,255,0.1)]"
              />
              <input
                type="text"
                value={formData.color}
                onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                className="flex-1 p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
                placeholder="#4a9eff"
                pattern="^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"
              />
            </div>
            <div className="flex gap-2 flex-wrap mt-2">
              {["#4a9eff", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"].map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setFormData({ ...formData, color })}
                  className="w-8 h-8 rounded border-2 border-[rgba(255,255,255,0.2)] hover:border-white transition-colors"
                  style={{ backgroundColor: color }}
                  title={color}
                />
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="enabled"
              checked={formData.enabled}
              onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              className="w-5 h-5 rounded cursor-pointer"
            />
            <label htmlFor="enabled" className="text-sm font-medium text-[rgb(156,156,156)] cursor-pointer">
              {t("enabled") || "Enabled"}
            </label>
          </div>

          <div className="flex gap-3 pt-4 border-t border-[rgba(255,255,255,0.1)]">
            <button
              type="submit"
              className={`flex-1 px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                hoveredButton === 'submit' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredButton('submit')}
              onMouseLeave={() => setHoveredButton(null)}
            >
              {editingTag ? t("update") || "Update" : t("create") || "Create"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className={`flex-1 px-8 py-3 rounded-full font-normal text-sm cursor-pointer border ${
                hoveredButton === 'cancel' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredButton('cancel')}
              onMouseLeave={() => setHoveredButton(null)}
            >
              {t("cancel") || "Cancel"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

