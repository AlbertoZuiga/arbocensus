import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createUser,
  deactivateUser,
  fetchUsers,
  updateUser,
} from "@/api/users.js";
import { getErrorMessage } from "@/lib/errors";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ROLE_OPTIONS = [
  { value: "surveyor", label: "Censador" },
  { value: "admin", label: "Administrador" },
];

function fullName(user) {
  const name = [user.first_name, user.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  return name || user.username || "—";
}

function emptyForm() {
  return {
    username: "",
    first_name: "",
    last_name: "",
    email: "",
    role: "surveyor",
    password: "",
  };
}

function UserFormDialog({ open, onOpenChange, user, onSubmit, isPending, error }) {
  const isEdit = Boolean(user);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    if (!open) return;
    setForm(
      user
        ? {
            username: user.username,
            first_name: user.first_name ?? "",
            last_name: user.last_name ?? "",
            email: user.email ?? "",
            role: user.role,
            password: "",
          }
        : emptyForm(),
    );
  }, [open, user]);

  function handleSubmit(event) {
    event.preventDefault();
    const payload = {
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      role: form.role,
    };
    if (!isEdit) payload.username = form.username;
    if (form.password) payload.password = form.password;
    onSubmit(payload);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>
              {isEdit ? "Editar usuario" : "Nuevo usuario"}
            </DialogTitle>
            <DialogDescription>
              {isEdit
                ? "Actualiza los datos del usuario."
                : "Crea un usuario para el sistema."}
            </DialogDescription>
          </DialogHeader>

          {!isEdit && (
            <div className="space-y-1.5">
              <Label htmlFor="username">Usuario</Label>
              <Input
                id="username"
                required
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="first_name">Nombre</Label>
              <Input
                id="first_name"
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="last_name">Apellido</Label>
              <Input
                id="last_name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Rol</Label>
            <Select
              value={form.role}
              onValueChange={(value) => setForm({ ...form, role: value })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">
              {isEdit ? "Nueva contraseña (opcional)" : "Contraseña"}
            </Label>
            <Input
              id="password"
              type="password"
              required={!isEdit}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>
                {getErrorMessage(error, "No se pudo guardar el usuario.")}
              </AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Usuarios() {
  const queryClient = useQueryClient();
  const [dialogUser, setDialogUser] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["users"] });

  const saveMutation = useMutation({
    mutationFn: (payload) =>
      dialogUser ? updateUser(dialogUser.id, payload) : createUser(payload),
    onSuccess: () => {
      invalidate();
      setDialogOpen(false);
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (id) => deactivateUser(id),
    onSuccess: invalidate,
  });

  const reactivateMutation = useMutation({
    mutationFn: (id) => updateUser(id, { is_active: true }),
    onSuccess: invalidate,
  });

  function openCreate() {
    setDialogUser(null);
    saveMutation.reset();
    setDialogOpen(true);
  }

  function openEdit(user) {
    setDialogUser(user);
    saveMutation.reset();
    setDialogOpen(true);
  }

  function handleDeactivate(user) {
    if (window.confirm(`¿Desactivar a ${fullName(user)}?`)) {
      deactivateMutation.mutate(user.id);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-2xl">Usuarios</CardTitle>
        <Button onClick={openCreate}>Nuevo usuario</Button>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-muted-foreground">Cargando…</p>}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {getErrorMessage(error, "No se pudieron cargar los usuarios.")}
            </AlertDescription>
          </Alert>
        )}
        {deactivateMutation.error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>
              {getErrorMessage(
                deactivateMutation.error,
                "No se pudo desactivar el usuario.",
              )}
            </AlertDescription>
          </Alert>
        )}
        {reactivateMutation.error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>
              {getErrorMessage(
                reactivateMutation.error,
                "No se pudo reactivar el usuario.",
              )}
            </AlertDescription>
          </Alert>
        )}
        {data && data.length === 0 && (
          <p className="text-muted-foreground">Aún no hay usuarios.</p>
        )}
        {data && data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    {fullName(user)}
                  </TableCell>
                  <TableCell>{user.email || "—"}</TableCell>
                  <TableCell>{user.role_display}</TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? "default" : "secondary"}>
                      {user.is_active ? "Activo" : "Inactivo"}
                    </Badge>
                  </TableCell>
                  <TableCell className="space-x-2 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(user)}
                    >
                      Editar
                    </Button>
                    {user.is_active ? (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeactivate(user)}
                        disabled={deactivateMutation.isPending}
                      >
                        Desactivar
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => reactivateMutation.mutate(user.id)}
                        disabled={reactivateMutation.isPending}
                      >
                        Reactivar
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <UserFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        user={dialogUser}
        onSubmit={(payload) => saveMutation.mutate(payload)}
        isPending={saveMutation.isPending}
        error={saveMutation.error}
      />
    </Card>
  );
}
