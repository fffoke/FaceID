package com.facepanel.repository;

import com.facepanel.model.Person;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

public interface PersonRepository extends JpaRepository<Person, Long> {
    List<Person> findByFaceEmbeddingIsNull();
    List<Person> findByNotifyTelegramTrue();
    List<Person> findByUpdatedAtAfter(LocalDateTime since);
    Optional<Person> findByFirstNameAndLastNameAndMiddleName(String firstName, String lastName, String middleName);
    Optional<Person> findByFirstNameAndLastName(String firstName, String lastName);
    List<Person> findByGenderIsNull();
    List<Person> findByGenderAndHiddenForIsmalFalse(String gender);

    /** Все участники группы — для удаления группы целиком. */
    List<Person> findByGroup(String group);

    /**
     * Персоны без группы: поле пустое либо не заполнено вовсе.
     * Запрос нативный — в JPQL "group" зарезервированное слово.
     */
    @Query(value = "select * from person where person_group is null or trim(person_group) = ''",
           nativeQuery = true)
    List<Person> findWithoutGroup();
}
