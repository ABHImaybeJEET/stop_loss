"use client";

import React, { Suspense } from "react";
import ChatTerminal from "@/components/chat/ChatTerminal";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <ChatTerminal />
      </Suspense>
    </ProtectedRoute>
  );
}
