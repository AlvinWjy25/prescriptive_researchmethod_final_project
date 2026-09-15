## station_status_information.csv

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

## station_status_log.csv
Kolom	    Tipe	Deskripsi
station_id	string	Key untuk join ke station_status_log.csv
name	    string	Nama lokasi stasiun
lat, lon	float	Koordinat geografis
capacity	int	    Total slot terpasang di stasiun itu (bikes + docks seharusnya ≈ capacity)
region_id	string	ID wilayah/borough (kalau tersedia di sistem)