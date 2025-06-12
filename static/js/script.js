/*
 * File: script.js
 * Deskripsi: Mengandung semua logika JavaScript untuk interaktivitas blog,
 * termasuk fitur mode gelap/terang dan tombol scroll-to-top.
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- Elemen DOM untuk Mode Tema ---
    const themeToggle = document.getElementById('theme-toggle'); // Tombol toggle mode
    const themeIcon = document.getElementById('theme-icon');     // Ikon bulan/matahari pada tombol
    const body = document.body;                                 // Elemen body untuk menerapkan kelas tema

    // --- Fungsi untuk Menerapkan Tema ---
    // Menerima parameter 'theme' ('dark' atau 'light')
    function applyTheme(theme) {
        if (theme === 'dark') {
            body.classList.add('dark-mode'); // Tambahkan kelas 'dark-mode' ke body
            themeIcon.classList.remove('fa-moon'); // Ganti ikon menjadi matahari
            themeIcon.classList.add('fa-sun');
            localStorage.setItem('theme', 'dark'); // Simpan preferensi tema di localStorage
        } else {
            body.classList.remove('dark-mode'); // Hapus kelas 'dark-mode' dari body
            themeIcon.classList.remove('fa-sun'); // Ganti ikon menjadi bulan
            themeIcon.classList.add('fa-moon');
            localStorage.setItem('theme', 'light'); // Simpan preferensi tema di localStorage
        }
    }

    // --- Inisialisasi Tema Saat Halaman Dimuat ---
    const savedTheme = localStorage.getItem('theme'); // Cek apakah ada preferensi tema tersimpan
    if (savedTheme) {
        // Jika ada preferensi tersimpan, terapkan tema tersebut
        applyTheme(savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        // Jika tidak ada di localStorage, cek preferensi sistem operasi pengguna
        applyTheme('dark');
    } else {
        // Default ke mode terang jika tidak ada preferensi yang ditemukan
        applyTheme('light');
    }

    // --- Event Listener untuk Tombol Toggle Tema ---
    if (themeToggle) { // Pastikan tombol ada sebelum menambahkan event listener
        themeToggle.addEventListener('click', () => {
            // Jika saat ini dalam mode gelap, beralih ke terang; jika tidak, beralih ke gelap
            if (body.classList.contains('dark-mode')) {
                applyTheme('light');
            } else {
                applyTheme('dark');
            }
        });
    }

    // --- Logika Tombol Scroll-to-Top ---
    const scrollToTopBtn = document.getElementById('scrollToTopBtn'); // Dapatkan elemen tombol

    // Tampilkan atau sembunyikan tombol saat pengguna menggulir halaman
    window.addEventListener('scroll', () => {
        // Tampilkan tombol jika posisi gulir lebih dari 100 piksel dari atas
        if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
            scrollToTopBtn.style.display = 'block';
        } else {
            scrollToTopBtn.style.display = 'none'; // Sembunyikan tombol
        }
    });

    // Tambahkan event listener untuk menggulir ke atas saat tombol diklik
    if (scrollToTopBtn) { // Pastikan tombol ada sebelum menambahkan event listener
        scrollToTopBtn.addEventListener('click', () => {
            // Gulir ke bagian paling atas halaman dengan efek halus
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
});
