import React, { useState, useMemo, useEffect } from "react";
import { TConversation, TTag } from "../../types";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getTags } from "../../modules/apiCalls";
import "./ConversationsTable.css";
import { IconAlertTriangle } from "@tabler/icons-react";

interface ConversationsTableProps {
  conversations: TConversation[];
}

export const ConversationsTable: React.FC<ConversationsTableProps> = ({ conversations }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [tags, setTags] = useState<TTag[]>([]);
  
  // Cargar tags al montar el componente
  useEffect(() => {
    const loadTags = async () => {
      try {
        const tagsData = await getTags();
        setTags(tagsData);
      } catch (error) {
        console.error("Error loading tags:", error);
      }
    };
    loadTags();
  }, []);
  
  // Crear un mapeo de ID a nombre y color de tag
  const tagMap = useMemo(() => {
    const map = new Map<number, { name: string; color: string }>();
    tags.forEach(tag => {
      map.set(tag.id, { 
        name: tag.title, 
        color: tag.color || "#4a9eff" 
      });
    });
    return map;
  }, [tags]);
  
  // Asegurar que conversations sea un array válido
  const safeConversations = Array.isArray(conversations) ? conversations : [];
  
  const [filters, setFilters] = useState({
    search: "",
    userId: "",
    sortBy: "newest" as "newest" | "oldest",
    dateFrom: "",
    dateTo: "",
    minMessages: "",
    maxMessages: "",
    hasTags: "" as "" | "yes" | "no",
    hasAlerts: "" as "" | "yes" | "no",
  });

  // Obtener lista única de usuarios para el filtro
  const uniqueUserIds = useMemo(() => {
    const userIds = safeConversations.map(conv => conv?.user_id).filter(Boolean);
    return Array.from(new Set(userIds)).sort((a, b) => a - b);
  }, [safeConversations]);

  const filteredConversations = useMemo(() => {
    let filtered = [...safeConversations];

    // Filtrar por búsqueda (en título, ID, tags, y summary)
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(conv => {
        const titleMatch = conv.title?.toLowerCase().includes(searchLower);
        const idMatch = conv.id.toLowerCase().includes(searchLower);
        const tagsMatch = conv.tags?.some(tagId => {
          const tagInfo = tagMap.get(tagId);
          return tagInfo?.name.toLowerCase().includes(searchLower) || false;
        });
        const summaryMatch = conv.summary?.toLowerCase().includes(searchLower);
        return titleMatch || idMatch || tagsMatch || summaryMatch;
      });
    }

    // Filtrar por usuario
    if (filters.userId) {
      filtered = filtered.filter(conv => conv.user_id.toString() === filters.userId);
    }

    // Filtrar por rango de fechas
    if (filters.dateFrom) {
      const fromDate = new Date(filters.dateFrom);
      filtered = filtered.filter(conv => new Date(conv.created_at) >= fromDate);
    }
    if (filters.dateTo) {
      const toDate = new Date(filters.dateTo);
      toDate.setHours(23, 59, 59, 999); // Incluir todo el día
      filtered = filtered.filter(conv => new Date(conv.created_at) <= toDate);
    }

    // Filtrar por número de mensajes
    if (filters.minMessages) {
      const min = parseInt(filters.minMessages, 10);
      filtered = filtered.filter(conv => (conv.number_of_messages || 0) >= min);
    }
    if (filters.maxMessages) {
      const max = parseInt(filters.maxMessages, 10);
      filtered = filtered.filter(conv => (conv.number_of_messages || 0) <= max);
    }

    // Filtrar por tags
    if (filters.hasTags === "yes") {
      filtered = filtered.filter(conv => conv.tags && conv.tags.length > 0);
    } else if (filters.hasTags === "no") {
      filtered = filtered.filter(conv => !conv.tags || conv.tags.length === 0);
    }

    // Filtrar por alertas
    if (filters.hasAlerts === "yes") {
      filtered = filtered.filter(conv => (conv.alerts_count || 0) > 0);
    } else if (filters.hasAlerts === "no") {
      filtered = filtered.filter(conv => !conv.alerts_count || conv.alerts_count === 0);
    }

    // Ordenar
    filtered.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return filters.sortBy === "newest" ? dateB - dateA : dateA - dateB;
    });

    return filtered;
  }, [safeConversations, filters, tagMap]);

  const clearFilters = () => {
    setFilters({
      search: "",
      userId: "",
      sortBy: "newest",
      dateFrom: "",
      dateTo: "",
      minMessages: "",
      maxMessages: "",
      hasTags: "",
      hasAlerts: "",
    });
  };

  return (
    <div className="conversations-table">
      {/* Filtros */}
      <div className="conversations-filters-section p-3 md:p-5">
        <h3 className="conversations-filters-title text-sm md:text-lg mb-3 md:mb-4">{t("filters")}</h3>
        <div className="conversations-filters gap-2 md:gap-4">
          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("search-by-keywords")}</label>
            <input
              type="text"
              className="conversations-filter-input text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              placeholder={t("search-by-keywords")}
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("user")}</label>
            <select
              className="conversations-filter-select text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              value={filters.userId}
              onChange={(e) => setFilters({ ...filters, userId: e.target.value })}
            >
              <option value="">{t("all-users")}</option>
              {uniqueUserIds.map(userId => (
                <option key={userId} value={userId.toString()}>
                  {t("user")} {userId}
                </option>
              ))}
            </select>
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("date-from")}</label>
            <input
              type="date"
              className="conversations-filter-input text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              value={filters.dateFrom}
              onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("date-to")}</label>
            <input
              type="date"
              className="conversations-filter-input text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              value={filters.dateTo}
              onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("min-messages")}</label>
            <input
              type="number"
              className="conversations-filter-input text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              placeholder="0"
              min="0"
              value={filters.minMessages}
              onChange={(e) => setFilters({ ...filters, minMessages: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("max-messages")}</label>
            <input
              type="number"
              className="conversations-filter-input text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              placeholder="∞"
              min="0"
              value={filters.maxMessages}
              onChange={(e) => setFilters({ ...filters, maxMessages: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("has-tags")}</label>
            <select
              className="conversations-filter-select text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              value={filters.hasTags}
              onChange={(e) => setFilters({ ...filters, hasTags: e.target.value as "" | "yes" | "no" })}
            >
              <option value="">{t("all")}</option>
              <option value="yes">{t("yes")}</option>
              <option value="no">{t("no")}</option>
            </select>
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("has-alerts")}</label>
            <select
              className="conversations-filter-select text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              value={filters.hasAlerts}
              onChange={(e) => setFilters({ ...filters, hasAlerts: e.target.value as "" | "yes" | "no" })}
            >
              <option value="">{t("all")}</option>
              <option value="yes">{t("yes")}</option>
              <option value="no">{t("no")}</option>
            </select>
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <label className="text-[10px] md:text-xs">{t("sort-by")}</label>
            <select
              className="conversations-filter-select text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5"
              value={filters.sortBy}
              onChange={(e) => setFilters({ ...filters, sortBy: e.target.value as "newest" | "oldest" })}
            >
              <option value="newest">{t("newest-first")}</option>
              <option value="oldest">{t("oldest-first")}</option>
            </select>
          </div>

          <div className="conversations-filter-group gap-1 md:gap-2">
            <button 
              className="conversations-clear-filters text-xs md:text-sm px-2 py-1.5 md:px-4 md:py-2.5 mt-2 md:mt-6"
              onClick={clearFilters}
            >
              {t("clear-filters")}
            </button>
          </div>
        </div>
      </div>

      {/* Tabla de conversaciones */}
      {filteredConversations.length === 0 ? (
        <div className="conversations-empty text-xs md:text-base py-8 md:py-[60px] px-3 md:px-5">
          {t("no-conversations")}
        </div>
      ) : (
        <div className="conversations-table-wrapper p-2 md:p-5">
          <div className="conversations-table-header text-xs md:text-sm py-2 md:py-3 mb-2 md:mb-4">
            <span>{t("showing")} {filteredConversations.length} {t("of")} {safeConversations.length} {t("conversations")}</span>
          </div>
          <table className="conversations-table-content text-xs md:text-sm">
            <thead>
              <tr>
                <th className="px-2 py-1.5 md:px-4 md:py-3 text-[10px] md:text-xs">{t("title")}</th>
                <th className="px-2 py-1.5 md:px-4 md:py-3 text-[10px] md:text-xs">{t("user")}</th>
                <th className="px-2 py-1.5 md:px-4 md:py-3 text-[10px] md:text-xs">{t("messages")}</th>
                <th className="px-2 py-1.5 md:px-4 md:py-3 text-[10px] md:text-xs">{t("date")}</th>
                <th className="px-2 py-1.5 md:px-4 md:py-3 text-[10px] md:text-xs">{t("tags")}</th>
                <th className="px-2 py-1.5 md:px-4 md:py-3 text-[10px] md:text-xs">{t("alerts")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredConversations.map(conv => (
                <tr 
                  key={conv.id}
                  onClick={() => navigate(`/chat?conversation=${conv.id}`)}
                  className="cursor-pointer hover:bg-[rgba(255,255,255,0.05)] transition-colors"
                >
                  <td className="conversation-title-cell px-2 py-1.5 md:px-4 md:py-3 text-xs md:text-sm max-w-[120px] md:max-w-[250px]">
                    {conv.title || conv.id.slice(0, 20) + "..."}
                  </td>
                  <td className="px-2 py-1.5 md:px-4 md:py-3 text-xs md:text-sm">{conv.user_id || "-"}</td>
                  <td className="px-2 py-1.5 md:px-4 md:py-3 text-xs md:text-sm">{conv.number_of_messages || 0}</td>
                  <td className="px-2 py-1.5 md:px-4 md:py-3 text-xs md:text-sm">{conv.created_at ? new Date(conv.created_at).toLocaleDateString() : "-"}</td>
                  <td className="px-2 py-1.5 md:px-4 md:py-3">
                    {conv.tags && conv.tags.length > 0 ? (
                      <div className="conversation-tags gap-1 md:gap-1.5">
                        {conv.tags.slice(0, 3).map((tagId, idx) => {
                          const tagInfo = tagMap.get(tagId);
                          if (!tagInfo) return null;
                          return (
                            <span 
                              key={idx} 
                              className="conversation-tag text-[10px] md:text-xs px-1.5 py-0.5 md:px-2 md:py-1"
                              style={{ backgroundColor: tagInfo.color }}
                            >
                              {tagInfo.name}
                            </span>
                          );
                        })}
                        {conv.tags.length > 3 && <span className="text-[10px] md:text-xs"> +{conv.tags.length - 3}</span>}
                      </div>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="px-2 py-1.5 md:px-4 md:py-3">
                    {(conv.alerts_count || 0) > 0 ? (
                      <div style={{ display: "flex", alignItems: "center", gap: "4px" }} className="md:gap-1.5">
                        <IconAlertTriangle size={12} />
                        <span className="text-xs md:text-sm">{conv.alerts_count}</span>
                      </div>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};