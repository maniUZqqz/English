// منوی موبایل
const menuToggle = document.querySelector('.menu-toggle');
const navLinks = document.querySelector('nav ul');

menuToggle.addEventListener('click', () => {
    navLinks.classList.toggle('active');
    menuToggle.classList.toggle('active');
});

// بستن منو هنگام کلیک روی لینک‌ها در موبایل
const navItems = document.querySelectorAll('nav ul li a');

navItems.forEach(item => {
    item.addEventListener('click', () => {
        if (navLinks.classList.contains('active')) {
            navLinks.classList.remove('active');
            menuToggle.classList.remove('active');
        }
    });
});

// تغییر هدر هنگام اسکرول
const header = document.getElementById('header');

window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }

    // نمایش دکمه بازگشت به بالا
    const backToTop = document.getElementById('back-to-top');
    if (window.scrollY > 300) {
        backToTop.style.display = 'block';
    } else {
        backToTop.style.display = 'none';
    }
});

// دکمه بازگشت به بالا
const backToTopButton = document.getElementById('back-to-top');

backToTopButton.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

// FAQ Accordion
const faqItems = document.querySelectorAll('.faq-item');

faqItems.forEach(item => {
    item.addEventListener('click', () => {
        faqItems.forEach(i => {
            if (i !== item) {
                i.classList.remove('active');
            }
        });
        item.classList.toggle('active');
    });
});

// AOS Initialization
AOS.init({
    duration: 800,
    once: true,
});

// اسلایدر نظرات کاربران
let currentTestimonial = 0;
const testimonials = document.querySelectorAll('.testimonial');

function showTestimonial(index) {
    testimonials.forEach((testimonial, i) => {
        testimonial.classList.remove('active');
        if (i === index) {
            testimonial.classList.add('active');
        }
    });
}

function nextTestimonial() {
    currentTestimonial = (currentTestimonial + 1) % testimonials.length;
    showTestimonial(currentTestimonial);
}

// اتوماتیک اسلاید
setInterval(nextTestimonial, 5000);

// نمایش اولین نظر
showTestimonial(currentTestimonial);

// مدیریت منوی آبشاری در موبایل
const dropdown = document.querySelector('.dropdown');
const dropbtn = dropdown.querySelector('.dropbtn');
const dropdownContent = dropdown.querySelector('.dropdown-content');

dropbtn.addEventListener('click', (e) => {
    e.preventDefault();
    dropdown.classList.toggle('active');
});
