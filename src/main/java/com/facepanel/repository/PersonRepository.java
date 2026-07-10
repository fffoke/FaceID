package com.facepanel.repository;

import com.facepanel.model.Person;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

public interface PersonRepository extends JpaRepository<Person, Long> {
    List<Person> findByFaceEmbeddingIsNull();
    List<Person> findByUpdatedAtAfter(LocalDateTime since);
    Optional<Person> findByFirstNameAndLastNameAndMiddleName(String firstName, String lastName, String middleName);
    Optional<Person> findByFirstNameAndLastName(String firstName, String lastName);
}
