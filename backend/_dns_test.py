import socket
print("db A records:", socket.getaddrinfo("db.wnwyegaiiwudqaahjyme.supabase.co", 5432, socket.AF_INET))
try:
    print("api4:", socket.getaddrinfo("wnwyegaiiwudqaahjyme.supabase.co", 443, socket.AF_INET))
except Exception as e:
    print("api4 err", e)
