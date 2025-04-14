/**
 * Main - Front Pages
 */
'use strict';

(function () {
  // Elements used in multiple functions
  const swiperLogos = document.getElementById('swiper-clients-logos');
  const swiperReviews = document.getElementById('swiper-reviews');
  const ReviewsPreviousBtn = document.getElementById('reviews-previous-btn');
  const ReviewsNextBtn = document.getElementById('reviews-next-btn');
  const ReviewsSliderPrev = document.querySelector('.swiper-button-prev');
  const ReviewsSliderNext = document.querySelector('.swiper-button-next');
  const priceDurationToggler = document.querySelector('.price-duration-toggler');
  const priceMonthlyList = [].slice.call(document.querySelectorAll('.price-monthly'));
  const priceYearlyList = [].slice.call(document.querySelectorAll('.price-yearly'));

  // LinguaConnect Slideshow
  const slideshow = document.getElementById('linguaconnect-slideshow');
  
  // Hero slideshow functionality
  if (slideshow) {
    const slides = slideshow.querySelectorAll('.hero-slide');
    const dots = slideshow.querySelectorAll('.dot');
    let currentSlide = 0;
    let slideInterval;

    // Initialize slideshow
    function startSlideshow() {
      slideInterval = setInterval(() => {
        nextSlide();
      }, 5000); // Change slide every 5 seconds
    }

    // Show specific slide
    function showSlide(index) {
      // Hide all slides
      slides.forEach(slide => {
        slide.classList.remove('active');
      });
      
      // Deactivate all dots
      dots.forEach(dot => {
        dot.classList.remove('active');
      });
      
      // Show current slide and activate corresponding dot
      slides[index].classList.add('active');
      dots[index].classList.add('active');
      
      // Reset the timer when manually changing slides
      clearInterval(slideInterval);
      startSlideshow();
    }

    // Next slide
    function nextSlide() {
      currentSlide = (currentSlide + 1) % slides.length;
      showSlide(currentSlide);
    }

    // Click handlers for dots
    dots.forEach((dot, index) => {
      dot.addEventListener('click', () => {
        showSlide(index);
        currentSlide = index;
      });
    });

    // Start the slideshow when the page loads
    startSlideshow();
  }

  // swiper carousel - Customers reviews
  // -----------------------------------
  if (swiperReviews) {
    new Swiper(swiperReviews, {
      slidesPerView: 1,
      spaceBetween: 0,
      grabCursor: true,
      autoplay: {
        delay: 3000,
        disableOnInteraction: false
      },
      loop: true,
      loopAdditionalSlides: 1,
      navigation: {
        nextEl: '.swiper-button-next',
        prevEl: '.swiper-button-prev'
      },
      breakpoints: {
        1200: {
          slidesPerView: 3
        },
        992: {
          slidesPerView: 2
        }
      }
    });
  }

  // Reviews slider next and previous
  // -----------------------------------
  if (ReviewsNextBtn && ReviewsSliderNext) {
    // Add click event listener to next button
    ReviewsNextBtn.addEventListener('click', function () {
      ReviewsSliderNext.click();
    });
  }
  
  if (ReviewsPreviousBtn && ReviewsSliderPrev) {
    ReviewsPreviousBtn.addEventListener('click', function () {
      ReviewsSliderPrev.click();
    });
  }

  // Review client logo
  // -----------------------------------
  if (swiperLogos) {
    new Swiper(swiperLogos, {
      slidesPerView: 2,
      autoplay: {
        delay: 3000,
        disableOnInteraction: false
      },
      breakpoints: {
        992: {
          slidesPerView: 5
        },
        768: {
          slidesPerView: 3
        }
      }
    });
  }

  // Pricing Plans
  // -----------------------------------
  document.addEventListener('DOMContentLoaded', function (event) {
    if (priceDurationToggler) {
      function togglePrice() {
        if (priceDurationToggler.checked) {
          // If checked
          priceYearlyList.map(function (yearEl) {
            yearEl.classList.remove('d-none');
          });
          priceMonthlyList.map(function (monthEl) {
            monthEl.classList.add('d-none');
          });
        } else {
          // If not checked
          priceYearlyList.map(function (yearEl) {
            yearEl.classList.add('d-none');
          });
          priceMonthlyList.map(function (monthEl) {
            monthEl.classList.remove('d-none');
          });
        }
      }
      
      // togglePrice Event Listener
      togglePrice();

      priceDurationToggler.onchange = function () {
        togglePrice();
      };
    }
  });
})();