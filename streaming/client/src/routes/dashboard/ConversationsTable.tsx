import React, { useState, useMemo } from "react";
import { TConversation } from "../../types";
import { useTranslation } from "react-i18next";
import "./ConversationsTable.css";

interface ConversationsTableProps {
  conversations: TConversation[];
}

export const ConversationsTable: React.FC<ConversationsTableProps> = ({ conversations }) => {
  const { t } = useTranslation();
  
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
        const tagsMatch = conv.tags?.some(tag => 
          tag.toLowerCase().includes(searchLower)
        );
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

    // Ordenar
    filtered.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return filters.sortBy === "newest" ? dateB - dateA : dateA - dateB;
    });

    return filtered;
  }, [safeConversations, filters]);

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
    });
  };

  return (
    <div className="conversations-table">
      {/* Filtros */}
      <div className="conversations-filters-section">
        <h3 className="conversations-filters-title">{t("filters")}</h3>
        <div className="conversations-filters">
          <div className="conversations-filter-group">
            <label>{t("search-by-keywords")}</label>
            <input
              type="text"
              className="conversations-filter-input"
              placeholder={t("search-by-keywords")}
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group">
            <label>{t("user")}</label>
            <select
              className="conversations-filter-select"
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

          <div className="conversations-filter-group">
            <label>{t("date-from")}</label>
            <input
              type="date"
              className="conversations-filter-input"
              value={filters.dateFrom}
              onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group">
            <label>{t("date-to")}</label>
            <input
              type="date"
              className="conversations-filter-input"
              value={filters.dateTo}
              onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group">
            <label>{t("min-messages")}</label>
            <input
              type="number"
              className="conversations-filter-input"
              placeholder="0"
              min="0"
              value={filters.minMessages}
              onChange={(e) => setFilters({ ...filters, minMessages: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group">
            <label>{t("max-messages")}</label>
            <input
              type="number"
              className="conversations-filter-input"
              placeholder="∞"
              min="0"
              value={filters.maxMessages}
              onChange={(e) => setFilters({ ...filters, maxMessages: e.target.value })}
            />
          </div>

          <div className="conversations-filter-group">
            <label>{t("has-tags")}</label>
            <select
              className="conversations-filter-select"
              value={filters.hasTags}
              onChange={(e) => setFilters({ ...filters, hasTags: e.target.value as "" | "yes" | "no" })}
            >
              <option value="">{t("all")}</option>
              <option value="yes">{t("yes")}</option>
              <option value="no">{t("no")}</option>
            </select>
          </div>

          <div className="conversations-filter-group">
            <label>{t("sort-by")}</label>
            <select
              className="conversations-filter-select"
              value={filters.sortBy}
              onChange={(e) => setFilters({ ...filters, sortBy: e.target.value as "newest" | "oldest" })}
            >
              <option value="newest">{t("newest-first")}</option>
              <option value="oldest">{t("oldest-first")}</option>
            </select>
          </div>

          <div className="conversations-filter-group">
            <button 
              className="conversations-clear-filters"
              onClick={clearFilters}
            >
              {t("clear-filters")}
            </button>
          </div>
        </div>
      </div>

      {/* Tabla de conversaciones */}
      {filteredConversations.length === 0 ? (
        <div className="conversations-empty">
          {t("no-conversations")}
        </div>
      ) : (
        <div className="conversations-table-wrapper">
          <div className="conversations-table-header">
            <span>{t("showing")} {filteredConversations.length} {t("of")} {safeConversations.length} {t("conversations")}</span>
          </div>
          <table className="conversations-table-content">
            <thead>
              <tr>
                <th>{t("title")}</th>
                <th>{t("user")}</th>
                <th>{t("messages")}</th>
                <th>{t("date")}</th>
                <th>{t("tags")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredConversations.map(conv => (
                <tr key={conv.id}>
                  <td className="conversation-title-cell">
                    {conv.title || conv.id.slice(0, 20) + "..."}
                  </td>
                  <td>{conv.user_id || "-"}</td>
                  <td>{conv.number_of_messages || 0}</td>
                  <td>{conv.created_at ? new Date(conv.created_at).toLocaleDateString() : "-"}</td>
                  <td>
                    {conv.tags && conv.tags.length > 0 ? (
                      <div className="conversation-tags">
                        {conv.tags.slice(0, 3).map((tag, idx) => (
                          <span key={idx} className="conversation-tag">{tag}</span>
                        ))}
                        {conv.tags.length > 3 && ` +${conv.tags.length - 3}`}
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