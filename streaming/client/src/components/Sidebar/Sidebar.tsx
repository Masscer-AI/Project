import React, { useEffect, useState } from "react"
import axios from "axios"
import "./Sidebar.css"
import { SVGS } from "../../assets/svgs"
import { API_URL } from "../../modules/constants"
import { useStore } from "../../modules/store"

interface TConversation {
  id: string
  user_id: number
  number_of_messages: number
  title: undefined | string
}

export const Sidebar: React.FC = () => {
  const { toggleSidebar } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
  }))

  const [conversations, setConversations] = useState<TConversation[]>([])

  useEffect(() => {
    populateHistory()
  }, [])

  const populateHistory = async () => {
    const token = localStorage.getItem("token")
    if (!token) {
      console.error("No token found in localStorage")
      return
    }

    try {
      const requestUrl = API_URL + "/v1/messaging/conversations"
      const res = await axios.get<TConversation[]>(requestUrl, {
        headers: {
          Authorization: `Token ${token}`,
        },
      })

      const conversations = res.data
      console.log(conversations)

      setConversations(conversations)
    } catch (error) {
      console.error("Failed to fetch conversations", error)
    }
  }

  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <button className="button">New chat</button>
        <button className="button" onClick={toggleSidebar}>
          {SVGS.burger}
        </button>
      </div>
      <div className="sidebar__history">
        {conversations.map((conversation) => (
          <ConversationComponent
            key={conversation.id}
            conversation={conversation}
          />
        ))}
      </div>
      <div className="sidebar__footer">Some user</div>
    </div>
  )
}

const ConversationComponent = ({
  conversation,
}: {
  conversation: TConversation
}) => {
  const { setConversation, toggleSidebar } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
  }))

  const handleClick = (e) => {
    e.preventDefault()
    setConversation(conversation.id)
    toggleSidebar()
  }

  return (
    <a
      href={`/chat/c/${conversation.id}`}
      className="conversation"
      onClick={handleClick}
    >
      {conversation.title ? (
        <p>{conversation.title}</p>
      ) : (
        <p>{conversation.id}</p>
      )}
    </a>
  )
}
