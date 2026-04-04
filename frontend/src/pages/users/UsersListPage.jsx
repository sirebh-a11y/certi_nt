import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

export default function UsersListPage() {
  const { token, user } = useAuth();
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    apiRequest("/users", {}, token)
      .then((data) => {
        if (!ignore) {
          setUsers(data.items);
        }
      })
      .catch((requestError) => {
        if (!ignore) {
          setError(requestError.message);
        }
      });

    return () => {
      ignore = true;
    };
  }, [token]);

  return (
    <section className="rounded-3xl border border-border bg-panel p-8 shadow-lg shadow-slate-200/40">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Utenti</p>
          <h2 className="mt-2 text-2xl font-semibold">Users List</h2>
        </div>
        {user?.role === "admin" ? (
          <Link className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700" to="/users/new">
            New User
          </Link>
        ) : null}
      </div>

      {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

      <div className="mt-6 overflow-hidden rounded-2xl border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">Nome</th>
              <th className="px-4 py-3 text-left font-semibold">Email</th>
              <th className="px-4 py-3 text-left font-semibold">Reparto</th>
              <th className="px-4 py-3 text-left font-semibold">Ruolo</th>
              <th className="px-4 py-3 text-left font-semibold">Stato</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-white">
            {users.map((item) => (
              <tr className="hover:bg-slate-50" key={item.id}>
                <td className="px-4 py-3">
                  <Link className="font-medium text-accent hover:underline" to={`/users/${item.id}`}>
                    {item.name}
                  </Link>
                </td>
                <td className="px-4 py-3">{item.email}</td>
                <td className="px-4 py-3">{item.department}</td>
                <td className="px-4 py-3">{item.role}</td>
                <td className="px-4 py-3">{item.active ? "Attivo" : "Disattivo"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
