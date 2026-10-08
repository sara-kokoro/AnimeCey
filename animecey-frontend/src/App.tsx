import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Home from "./pages/Home.tsx";
import AnimeDetail from "./pages/AnimeDetail.tsx";
import Watch from "./pages/Watch.tsx";
import Search from "./pages/Search.tsx";
import Catalogue from "./pages/Catalogue.tsx";
import Genres from "./pages/Genres.tsx";
import Calendrier from "./pages/Calendrier.tsx";
import Auth from "./pages/Auth.tsx";
import Profile from "./pages/Profile.tsx";
import Notifications from "./pages/Notifications.tsx";
import { AdminLayout } from "./components/admin/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard.tsx";
import AdminAnimes from "./pages/admin/AdminAnimes.tsx";
import AdminFolders from "./pages/admin/AdminFolders.tsx";
import AdminUsers from "./pages/admin/AdminUsers.tsx";
import AdminBroadcast from "./pages/admin/AdminBroadcast.tsx";
import AdminComments from "./pages/admin/AdminComments.tsx";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/anime/:id" element={<AnimeDetail />} />
          <Route path="/watch/:id" element={<Watch />} />
          <Route path="/search" element={<Search />} />
          <Route path="/catalogue" element={<Catalogue />} />
          <Route path="/films" element={<Catalogue presetType="film" title="Films" subtitle="Longs métrages : animation et prises de vue réelles." />} />
          <Route path="/series" element={<Catalogue presetType="serie" title="Séries" subtitle="Des sagas épiques aux tranches de vie intimistes." />} />
          <Route path="/genres" element={<Genres />} />
          <Route path="/calendrier" element={<Calendrier />} />
          <Route path="/genre/:slug" element={<Catalogue />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="animes" element={<AdminAnimes />} />
            <Route path="folders" element={<AdminFolders />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="broadcast" element={<AdminBroadcast />} />
            <Route path="comments" element={<AdminComments />} />
          </Route>
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
