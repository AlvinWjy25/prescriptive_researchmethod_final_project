Kolom	            Tipe	        Deskripsi
polled_at	        timestamp	    Waktu script kamu melakukan request (UTC, ISO format)
station_id	        string	        ID unik stasiun
num_bikes_available	int	            Jumlah sepeda reguler siap disewa saat itu — ini "inventory level" utama
num_bikes_disabled	int	            Sepeda yang ada fisik tapi rusak/tidak bisa disewa
num_docks_available	int	            Slot kosong untuk parkir sepeda — proxy kapasitas sisa
num_docks_disabled	int	            Slot rusak/tidak bisa dipakai
num_ebikes_available int	        Subset e-bike dari num_bikes_available
is_installed	    0/1	            Apakah stasiun fisik terpasang (0 = sedang dibongkar/dipindah)
is_renting	        0/1	            Apakah stasiun sedang menerima peminjaman
is_returning	    0/1	            Apakah stasiun sedang menerima pengembalian
last_reported	    unix timestamp	Kapan API/sensor stasiun itu terakhir update datanya (bukan waktu kamu polling) — ini yang dipakai untuk dedup logic